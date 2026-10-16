# Prueba real de SageAttention en la GPU. Sale con 0 solo si funciona y coincide con la atencion normal.
import sys

try:
    import torch
    import torch.nn.functional as F
    from sageattention import sageattn

    q, k, v = (torch.randn(1, 24, 1024, 128, device="cuda", dtype=torch.bfloat16) for _ in range(3))
    out = sageattn(q, k, v, tensor_layout="HND", is_causal=False)
    ref = F.scaled_dot_product_attention(q, k, v)
    sim = F.cosine_similarity(out.float().flatten(), ref.float().flatten(), dim=0).item()
    print(f"    SageAttention similitud con PyTorch: {sim:.4f}")
    sys.exit(0 if sim > 0.99 else 1)
except Exception as e:
    print(f"    SageAttention fallo: {type(e).__name__}: {e}")
    sys.exit(1)
