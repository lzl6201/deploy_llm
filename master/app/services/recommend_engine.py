"""自动部署推荐引擎 v2（显存 / 量化 / 引擎感知）。

根据模型元数据（格式、参数量、量化档位、实际文件大小、KV 结构）与目标
GPU 显存，估算权重 + KV cache + 激活的显存占用，推荐最优部署方案：
引擎、并行度（单卡 / 多卡层切分）、推荐上下文长度与量化档位，并给出
备选方案（更高压缩 / 多卡）。

GGUF 模型按「实际文件大小」精确估算权重显存；Safetensors 模型按参数量 ×
每参数字节估算。KV cache 依据 attention 头结构计算，缺失时退化为经验系数。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Safetensors 量化档位每参数近似字节数（vLLM 系）
BYTES_PER_PARAM = {
    "none": 2,
    "bf16": 2,
    "fp16": 2,
    "fp8": 1,
    "int8": 1,
    "awq": 0.5,
    "awq-int4": 0.5,
    "gptq": 0.5,
    "squeezellm": 0.5,
}

# GGUF 量化档位每参数近似 bit 数（用于生成备选方案时的文件大小估算）
GGUF_BITS = {
    "F32": 32.0, "F16": 16.0, "Q8_0": 8.5, "Q6_K": 6.5625,
    "Q5_K_M": 5.75, "Q5_K_S": 5.5, "Q4_K_M": 4.75, "Q4_K_S": 4.5,
    "Q3_K_L": 3.875, "Q3_K_M": 3.6875, "Q3_K_S": 3.4375, "Q2_K": 2.5625,
}

# 权重之外（激活 / 运行时缓冲）占权重显存的经验比例
# llama.cpp 推理运行时开销小；vLLM 因 CUDA graph / 分页 KV 等开销更大
OVERHEAD_RATIO_GGUF = 0.06
OVERHEAD_RATIO_VLLM = 0.15

# 可用的显存占比（预留系统 / 其他进程占用）
USABLE_RATIO_GGUF = 0.95
USABLE_RATIO_VLLM = 0.90

MIN_CTX = 4096
KB = 1024
MB = 1024 * 1024


@dataclass
class RecommendInput:
    params_b: float = 0.0
    dtype: str = "bf16"
    context_len: int = 4096
    quantization: str = "none"
    format: str = "safetensors"  # gguf / safetensors / ollama
    file_size_mb: int = 0
    gpus: list[dict] | None = None
    # GGUF KV 结构（用于精确 KV cache 估算），缺失时退化
    block_count: int = 0
    head_count_kv: int = 0
    key_length: int = 0
    embedding_length: int = 0


@dataclass
class Plan:
    engine: str
    tp_size: int
    quantization: str
    ctx_len: int
    weight_mb: int
    kv_cache_mb: int
    overhead_mb: int
    total_mb: int
    fits: bool
    note: str


@dataclass
class RecommendResult:
    engine: str
    tp_size: int
    quantization: str
    fits_single_gpu: bool
    fits: bool  # 是否能在目标节点部署（单卡或多卡均算）
    estimated_vram_mb: int
    weight_mb: int
    kv_cache_mb: int
    recommended_ctx_len: int
    note: str
    alternatives: list[dict] = field(default_factory=list)


def _weight_mb(inp: RecommendInput, quantization: str) -> int:
    """估算指定量化档位下的权重大小（MB）。"""
    if inp.format == "gguf":
        # 有实际文件大小时以实际为准；否则按参数量 × bit 估算
        if inp.file_size_mb and quantization == inp.quantization:
            return inp.file_size_mb
        bits = GGUF_BITS.get(quantization)
        if bits:
            return int(inp.params_b * 1e9 * bits / 8 / MB)
        return inp.file_size_mb or 0
    bpp = BYTES_PER_PARAM.get(quantization, BYTES_PER_PARAM["none"])
    return int(inp.params_b * 1e9 * bpp / MB)


def _kv_per_token_bytes(inp: RecommendInput) -> float:
    """每个 token 的 KV cache 字节数（K+V，F16）。"""
    if inp.block_count <= 0:
        return 0.0
    if inp.head_count_kv > 0 and inp.key_length > 0:
        kv_dim = inp.head_count_kv * inp.key_length
    elif inp.head_count_kv > 0 and inp.embedding_length > 0:
        kv_dim = inp.head_count_kv * (inp.embedding_length // inp.head_count_kv)
    elif inp.embedding_length > 0:
        kv_dim = inp.embedding_length // 4  # GQA 经验比
    else:
        return 0.0
    return 2.0 * inp.block_count * kv_dim * 2  # K+V 两份 × F16 两字节


def _kv_cache_mb(inp: RecommendInput, ctx_len: int) -> int:
    return int(_kv_per_token_bytes(inp) * ctx_len / MB)


def _engine_for(inp: RecommendInput) -> str:
    if inp.format == "gguf":
        return "llama.cpp"
    if inp.format == "ollama":
        return "ollama"
    return "vllm"


def _overhead_ratio(inp: RecommendInput) -> float:
    return OVERHEAD_RATIO_GGUF if inp.format == "gguf" else OVERHEAD_RATIO_VLLM


def _usable_ratio(inp: RecommendInput) -> float:
    return USABLE_RATIO_GGUF if inp.format == "gguf" else USABLE_RATIO_VLLM


def _build_plan(inp: RecommendInput, tp: int, quant: str, ctx: int, gpu_vram: list[int]) -> Plan:
    weight = _weight_mb(inp, quant)
    kv = _kv_cache_mb(inp, ctx)
    overhead = int(weight * _overhead_ratio(inp))
    total = weight + kv + overhead
    capacity = sum(gpu_vram[:tp]) if tp <= len(gpu_vram) else sum(gpu_vram)
    min_gpu = min(gpu_vram[:tp]) if tp <= len(gpu_vram) else 0
    usable_ratio = _usable_ratio(inp)
    # 层切分（llama.cpp）以总显存为准；张量并行（vLLM）以最小卡为准
    usable = capacity * usable_ratio
    if inp.format == "gguf":
        fits = total <= usable  # llama.cpp 层切分，按合计显存
    else:
        fits = total / tp <= min_gpu * usable_ratio if tp <= len(gpu_vram) else False
    note = f"{quant} · 权重{weight/1024:.1f}G + KV({ctx}){kv/1024:.2f}G + 开销{overhead/1024:.2f}G"
    return Plan(
        engine=_engine_for(inp), tp_size=tp, quantization=quant, ctx_len=ctx,
        weight_mb=weight, kv_cache_mb=kv, overhead_mb=overhead,
        total_mb=total, fits=fits, note=note,
    )


def _max_ctx_for(inp: RecommendInput, tp: int, quant: str, gpu_vram: list[int]) -> int:
    """在当前并行度/量化下，能容纳的最大上下文长度。"""
    weight = _weight_mb(inp, quant)
    overhead = int(weight * _overhead_ratio(inp))
    capacity = sum(gpu_vram[:tp]) if tp <= len(gpu_vram) else sum(gpu_vram)
    usable = capacity * _usable_ratio(inp) - weight - overhead
    per_token = _kv_per_token_bytes(inp)
    if per_token <= 0:
        return inp.context_len or MIN_CTX
    budget_tokens = int(usable * MB / per_token)
    return max(MIN_CTX, min(inp.context_len or budget_tokens, budget_tokens))


def recommend(inp: RecommendInput) -> RecommendResult:
    gpus = sorted(
        [g.get("vram_total_mb", 0) for g in (inp.gpus or [])], reverse=True
    )
    quant = inp.quantization or ("none" if inp.format != "gguf" else "F16")
    engine = _engine_for(inp)

    if not gpus:
        weight = _weight_mb(inp, quant)
        total = int(weight * (1 + _overhead_ratio(inp)))
        return RecommendResult(
            engine=engine, tp_size=1, quantization=quant, fits_single_gpu=True, fits=True,
            estimated_vram_mb=total, weight_mb=weight, kv_cache_mb=0,
            recommended_ctx_len=MIN_CTX,
            note="未提供 GPU 显存信息，按权重估算", alternatives=[],
        )

    # 单卡拟合
    ctx_1 = _max_ctx_for(inp, 1, quant, gpus)
    plan1 = _build_plan(inp, 1, quant, ctx_1, gpus)
    if plan1.fits:
        return RecommendResult(
            engine=engine, tp_size=1, quantization=quant, fits_single_gpu=True, fits=True,
            estimated_vram_mb=plan1.total_mb, weight_mb=plan1.weight_mb,
            kv_cache_mb=plan1.kv_cache_mb, recommended_ctx_len=ctx_1,
            note="单卡显存可容纳，推荐单卡部署", alternatives=_alternatives(inp, gpus, quant),
        )

    # 多卡层切分 / TP
    for tp in (2, 4, 8):
        if len(gpus) >= tp:
            ctx_n = _max_ctx_for(inp, tp, quant, gpus)
            plan_n = _build_plan(inp, tp, quant, ctx_n, gpus)
            if plan_n.fits:
                return RecommendResult(
                    engine=engine, tp_size=tp, quantization=quant,
                    fits_single_gpu=False, fits=True, estimated_vram_mb=plan_n.total_mb,
                    weight_mb=plan_n.weight_mb, kv_cache_mb=plan_n.kv_cache_mb,
                    recommended_ctx_len=ctx_n,
                    note=f"单卡放不下，推荐 {tp} 卡并行部署",
                    alternatives=_alternatives(inp, gpus, quant),
                )

    # 仍放不下：尝试更高压缩档位
    alt = _alternatives(inp, gpus, quant)
    fitting = next((a for a in alt if a.get("fits")), None)
    if fitting:
        return RecommendResult(
            engine=engine, tp_size=fitting["tp_size"], quantization=fitting["quantization"],
            fits_single_gpu=fitting["tp_size"] == 1, fits=True,
            estimated_vram_mb=fitting["total_mb"],
            weight_mb=fitting["weight_mb"], kv_cache_mb=fitting["kv_cache_mb"],
            recommended_ctx_len=fitting["ctx_len"],
            note="当前档位放不下，已为你切换更小量化档位", alternatives=alt,
        )

    return RecommendResult(
        engine=engine, tp_size=len(gpus), quantization=quant, fits_single_gpu=False, fits=False,
        estimated_vram_mb=plan1.total_mb, weight_mb=plan1.weight_mb,
        kv_cache_mb=plan1.kv_cache_mb, recommended_ctx_len=MIN_CTX,
        note="超出全部节点显存容量，需增加 GPU 或跨机扩展", alternatives=alt,
    )


def _alternatives(inp: RecommendInput, gpus: list[int], current: str) -> list[dict]:
    """生成备选方案：按压缩度从高到低（文件从小到大）排列，可行方案优先。"""
    if inp.format == "gguf":
        # 按 bit 数升序：更小（更压缩）的档位在前
        candidates = sorted(
            (q for q in GGUF_BITS if q != current),
            key=lambda q: GGUF_BITS[q],
        )
    else:
        candidates = [q for q in BYTES_PER_PARAM if q != current and q not in ("none", "bf16", "fp16")]
    result = []
    for q in candidates[:8]:
        for tp in (1, 2, 4):
            if tp > len(gpus):
                continue
            ctx = _max_ctx_for(inp, tp, q, gpus)
            plan = _build_plan(inp, tp, q, ctx, gpus)
            result.append({
                "engine": _engine_for(inp), "tp_size": tp, "quantization": q,
                "ctx_len": ctx, "weight_mb": plan.weight_mb, "kv_cache_mb": plan.kv_cache_mb,
                "total_mb": plan.total_mb, "fits": plan.fits,
            })
    result.sort(key=lambda a: (not a["fits"], a["total_mb"]))
    return result
