# Transformer 架构详解

> 学习日期：2026-05-29
> 论文：[Attention Is All You Need](https://arxiv.org/abs/1706.03762) (Vaswani et al., 2017)

---

## 1. 为什么需要 Transformer？

### 1.1 之前模型的局限性

| 模型 | 缺点 |
|------|------|
| **RNN / LSTM** | 串行计算，无法并行；长距离依赖容易丢失，梯度消失/爆炸 |
| **CNN** | 感受野有限，需要堆叠多层才能捕捉长距离依赖 |
| **Seq2Seq + Attention** | 虽然引入了 Attention，但主体仍是 RNN，无法并行 |

### 1.2 Transformer 的核心突破

- **完全基于 Attention 机制**，摒弃循环/卷积结构
- **并行计算**：所有 token 同时计算
- **长距离依赖**：Attention 直接计算任意两个位置的关系
- **可扩展性**：更大的模型 + 更多的数据 = 更强的能力（Scaling Law）

---

## 2. 整体架构

```
                           ┌───────────────────────┐
                           │   Output Probabilities │
                           └───────────┬───────────┘
                                       │
                                  ┌────▼────┐
                                  │  Linear  │
                                  └────┬────┘
                                       │
                                  ┌────▼────┐
                                  │  Softmax │
                                  └────┬────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │          Add & Norm                  │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │        Feed Forward                  │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │          Add & Norm                  │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │     Multi-Head Attention             │
                    │        (Masked)                      │
                    └──────────────────┬──────────────────┘
                                       │
                              ┌────────┴────────┐
                              │  Positional      │
                              │   Encoding       │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │  Input Embedding │◄── Outputs (shifted right)
                              └─────────────────┘

                    ┌──────────────────┴──────────────────┐
                    │          Add & Norm                  │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │        Feed Forward                  │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │          Add & Norm                  │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │     Multi-Head Attention             │
                    └──────────────────┬──────────────────┘
                                       │
                              ┌────────┴────────┐
                              │  Positional      │
                              │   Encoding       │
                              └────────┬────────┘
                                       │
                              ┌────────┴────────┐
                              │  Input Embedding │◄── Inputs
                              └─────────────────┘
```

### 2.1 两大核心模块

| 模块 | 作用 |
|------|------|
| **Encoder**（左侧） | 将输入序列编码为表示向量，双向注意力（每个位置能看到所有位置） |
| **Decoder**（右侧） | 根据 Encoder 输出 + 已生成内容，逐步生成目标序列，带 Masked Attention |

### 2.2 Transformer 的 6 个关键组件

1. **Input Embedding** — 将 token 映射为向量
2. **Positional Encoding** — 注入位置信息
3. **Multi-Head Self-Attention** — 捕捉序列内关系
4. **Feed-Forward Network (FFN)** — 非线性变换
5. **Add & Norm（残差连接 + Layer Normalization）** — 稳定训练
6. **Masked Attention** — Decoder 中防止看到未来信息

---

## 3. 核心组件详解

### 3.1 Embedding（嵌入层）

将离散的 token（词/子词）映射到连续的向量空间。

```python
# 简单理解：查表操作
embedding_matrix = nn.Embedding(vocab_size=30000, d_model=512)
x = embedding_matrix(token_ids)  # shape: (batch, seq_len, 512)
```

### 3.2 Positional Encoding（位置编码）

因为 Attention 本身不感知 token 顺序，需要注入位置信息。

**公式：**
```
PE(pos, 2i)   = sin(pos / 10000^(2i / d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i / d_model))
```

- `pos`：token 在序列中的位置
- `i`：维度索引
- `d_model`：模型维度（如 512）

**特性：**
- 每个位置有唯一的编码
- 不同位置的编码可以相对偏移
- 能外推到比训练时更长的序列（有限）
- 后来的模型多用 **可学习的位置编码**（Learnable Positional Encoding）

```python
# 代码实现
import torch
import math

def positional_encoding(max_len, d_model):
    pe = torch.zeros(max_len, d_model)
    position = torch.arange(0, max_len).unsqueeze(1)
    div_term = torch.exp(torch.arange(0, d_model, 2) * -(math.log(10000.0) / d_model))
    pe[:, 0::2] = torch.sin(position * div_term)
    pe[:, 1::2] = torch.cos(position * div_term)
    return pe  # shape: (max_len, d_model)
```

#### RoPE (Rotary Position Embedding) — 现代 LLM 的主流方案

LLaMA、Mistral、Gemma 等主流模型使用 RoPE 而非原始 Sinusoidal PE。

**核心思想**：在 Attention 计算中对 Q 和 K 向量施加旋转矩阵，使得 Q·Kᵀ 的结果自然包含相对位置信息。

**优点**：
- 天然支持相对位置（不是绝对位置）
- 更好的长度外推能力
- 随着距离增大，注意力权重自然衰减

### 3.3 Scaled Dot-Product Attention（缩放点积注意力）

**公式：**
```
Attention(Q, K, V) = softmax(Q · Kᵀ / √d_k) · V
```

**计算步骤：**
1. Q × Kᵀ → 计算相似度得分矩阵
2. 除以 √d_k → 缩放，防止 softmax 梯度消失
3. softmax → 归一化为注意力权重
4. 权重 × V → 加权求和得到输出

```python
def scaled_dot_product_attention(Q, K, V, mask=None):
    """
    Q, K, V: (batch, seq_len, d_k)
    """
    d_k = Q.size(-1)
    scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_k)
    # scores shape: (batch, seq_len, seq_len)
    
    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))
    
    attn_weights = torch.softmax(scores, dim=-1)
    output = torch.matmul(attn_weights, V)
    return output, attn_weights
```

**为什么除以 √d_k？**

当 d_k 很大时，Q·Kᵀ 的值会很大（方差 ≈ d_k），导致 softmax 进入梯度极小区域。除以 √d_k 可以让方差稳定在 1 左右。

### 3.4 Multi-Head Attention（多头注意力）

**思路**：用多组 Q/K/V 并行计算，捕捉不同子空间的语义特征。

```
MultiHead(Q, K, V) = Concat(head₁, ..., headₕ) · W_O
  其中 headᵢ = Attention(Q·W_Qⁱ, K·W_Kⁱ, V·W_Vⁱ)
```

```python
class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, num_heads):
        super().__init__()
        self.num_heads = num_heads
        self.d_k = d_model // num_heads  # 每个头的维度
        
        self.W_Q = nn.Linear(d_model, d_model)
        self.W_K = nn.Linear(d_model, d_model)
        self.W_V = nn.Linear(d_model, d_model)
        self.W_O = nn.Linear(d_model, d_model)
    
    def forward(self, Q, K, V, mask=None):
        batch_size = Q.size(0)
        
        # 1. 线性变换 + 分头
        Q = self.W_Q(Q).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_K(K).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_V(V).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        # shape: (batch, num_heads, seq_len, d_k)
        
        # 2. 每个头独立计算 Attention
        attn_output, _ = scaled_dot_product_attention(Q, K, V, mask)
        # shape: (batch, num_heads, seq_len, d_k)
        
        # 3. 合并多头
        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, -1, self.num_heads * self.d_k)
        # shape: (batch, seq_len, d_model)
        
        # 4. 输出投影
        return self.W_O(attn_output)
```

**典型配置**：d_model=512, num_heads=8 → 每头 d_k=64

### 3.5 三种 Attention 类型

| 类型 | 位置 | Q | K | V | 特点 |
|------|------|---|---|---|------|
| **Self-Attention** | Encoder | X | X | X | 每个 token 看所有 token（双向） |
| **Masked Self-Attention** | Decoder | X | X | X | 每个 token 只能看自己和前面的 token（单向） |
| **Cross-Attention** | Decoder | Decoder输入 | Encoder输出 | Encoder输出 | Decoder 看 Encoder 的输出 |

### 3.6 Feed-Forward Network（前馈网络）

每个 token 位置独立的双层 MLP：

```
FFN(x) = max(0, x·W₁ + b₁)·W₂ + b₂
```

也等价于两层线性变换 + ReLU 激活：

```
FFN(x) = W₂ · ReLU(W₁·x + b₁) + b₂
```

**典型配置**：
- d_model = 512
- d_ff = 2048（约为 4 倍 d_model）
- 参数量：512×2048 + 2048×512 ≈ 2.1M

**现代变体**（LLaMA 等使用）：
- **SwiGLU**：`FFN(x) = (Swish(x·W₁) ⊙ x·V₁)·W₂`
- 比 ReLU 训练更稳定，效果更好

### 3.7 Add & Norm（残差连接 + 层归一化）

```
output = LayerNorm(x + Sublayer(x))
```

**残差连接（Residual Connection / Skip Connection）**：
- 缓解梯度消失，让深层网络更容易训练
- 每个子层（Attention / FFN）都包一层 Add & Norm

**Layer Normalization（层归一化）**：
- 对每个样本的所有特征维度做归一化
- `LayerNorm(x) = (x - μ) / √(σ² + ε) × γ + β`
- 相比 BatchNorm，LayerNorm 不受 batch size 影响，更适合 NLP

**Pre-Norm vs Post-Norm**：

| 方式 | 公式 | 使用模型 |
|------|------|---------|
| Post-Norm（原始） | `LayerNorm(x + Sublayer(x))` | 原始 Transformer |
| Pre-Norm（现代） | `x + Sublayer(LayerNorm(x))` | GPT, LLaMA, BERT 等几乎全部现代模型 |

Pre-Norm 训练更稳定，收敛更快，是现在的主流选择。

---

## 4. 训练细节

### 4.1 标签平滑（Label Smoothing）
- 防止模型过于自信
- 真实标签的 one-hot 分布中加入少量噪声

### 4.2 Warmup + Decay 学习率调度
```
lr = d_model^(-0.5) × min(step^(-0.5), step × warmup_steps^(-1.5))
```
- 先线性 warmup（学习率从 0 上升）
- 再按 step^(-0.5) 衰减

### 4.3 Dropout
- 在每个子层输出、Embedding、Attention 权重上使用
- 原始论文 p=0.1

---

## 5. 为什么 Attention 能 work？

**直觉理解**：Attention 让模型在处理每个词时，能「看」到序列中所有其他词，并根据相关性加权聚合信息。

```
例句: "The animal didn't cross the street because it was too tired."
                       ↑
                     "it" 指的是谁？→ Animal 还是 Street？
                     Attention 帮模型回答：是 Animal（因为 tired）
```

- "it" 的 Query 会与 "animal" 的 Key 产生高相似度得分
- 所以 Attention 权重集中在 "animal" 上
- 聚合的 Value 中 "animal" 的信息占主导

---

## 6. Transformer 的参数量估算

```
Total params = Embedding_params + Encoder×N + Decoder×N + Output_projection

每层 Encoder：
  Multi-Head Attention: 4 × d_model²（Q/K/V/O 四个矩阵）
  FFN: 2 × d_model × d_ff

每层 Decoder：
  Masked Attention: 4 × d_model²
  Cross Attention:  4 × d_model²
  FFN: 2 × d_model × d_ff
```

**以 BERT-Base 为例**：L=12, d_model=768, d_ff=3072, num_heads=12
- Embedding: 30000 × 768 = 23M
- 每层 Encoder: 4×768² + 2×768×3072 = 2.36M + 4.72M = 7.08M
- 12 层: 12 × 7.08M = 84.9M
- 总计 ≈ 110M（与官方 110M 吻合）

---

## 7. 局限与改进

### 局限
1. **O(n²) 计算复杂度** — 长序列计算量巨大
2. **没有位置信息的先验** — 需要靠位置编码
3. **难以外推到更长序列** — 相对位置编码（RoPE, ALiBi）部分缓解
4. **缺少归纳偏置** — 比 CNN 需要更多数据才能收敛

### 主流改进

| 方向 | 代表工作 | 核心思想 |
|------|---------|---------|
| **高效 Attention** | FlashAttention, Linear Attention | 减少复杂度 |
| **长上下文** | Longformer, BigBird | 稀疏 Attention |
| **位置编码** | RoPE (LLaMA), ALiBi (Mosaic) | 更好的长度外推 |
| **架构改进** | LLaMA (SwiGLU, RMSNorm), GPT | 更稳定的训练 |
| **推理优化** | KV Cache, Speculative Decoding | 加速生成 |

---

## 8. 面试题与参考答案

### 面试题 1：Transformer 中为什么用 Scaled Dot-Product Attention 而不是直接用 Dot-Product？

**答**：当 d_k 较大时，点积 Q·Kᵀ 的值会很大（均值为 0，方差为 d_k），导致 softmax 的梯度进入平缓区域（梯度极小），不利于训练。除以 √d_k 将方差归一化到 1，让 softmax 梯度保持在合理范围。

### 面试题 2：Multi-Head Attention 为什么比 Single-Head 好？

**答**：多个头可以关注不同子空间的信息。例如一个头关注语法关系（主谓宾），另一个头关注语义关系（指代），还有一个头关注位置关系。分开学习比一个头把所有信息压在一起效果好。每个头的维度 d_k = d_model / h，总参数量不变，但表达能力更强。

### 面试题 3：为什么 Transformer 需要 Positional Encoding？

**答**：Attention 机制本身对位置不敏感——如果把句子中的词打乱顺序，Self-Attention 的计算结果不变。但自然语言中词序对语义至关重要（"猫追狗" vs "狗追猫"）。位置编码就是给模型注入「位置」信息的桥梁。

### 面试题 4：Layer Normalization 和 Batch Normalization 的区别？

**答**：
- **BatchNorm**：对每个特征维度在整个 batch 上做归一化。依赖 batch size，NLP batch size 通常不大，效果差。推理时需要维护 running mean/var。
- **LayerNorm**：对每个样本的所有特征维度做归一化。不依赖 batch size，训练和推理行为一致。NLP 任务中 LayerNorm 效果显著优于 BatchNorm。

### 面试题 5：Transformer 的参数量怎么算？（面试高频）

**答**：以原始 Transformer-Base 为例（d_model=512, d_ff=2048, h=8, L=6, vocab=37000）：
- Embedding: vocab × d_model = 37000 × 512 ≈ 18.9M
- 每层 Encoder Attention: 4 × d_model² = 4 × 512² ≈ 1.05M
- 每层 Encoder FFN: 2 × d_model × d_ff = 2 × 512 × 2048 ≈ 2.1M
- 每层 Decoder Attention: 4 × d_model² × 2 = 2.1M（Masked + Cross）
- 每层 Decoder FFN: 2 × 512 × 2048 ≈ 2.1M
- Decoder 每层: 2.1M + 2.1M = 4.2M
- 6 Encoder + 6 Decoder: 6×3.15M + 6×4.2M = 44.1M
- 总计 ≈ 63M（与论文的 65M 接近）

### 面试题 6：Transformer Decoder 中的 Masked Attention 是怎么实现的？

**答**：在 softmax 之前，将未来位置的得分设置为 -∞（对应 mask 矩阵的上三角部分）。这样 softmax 后这些位置的注意力权重为 0。具体实现：先生成一个上三角 mask 矩阵，在计算注意力分数后执行 `scores = scores.masked_fill(mask == 0, float('-inf'))`，再进行 softmax。这样保证了自回归生成时不会看到未来的 token。

### 面试题 7：为什么 BERT 只用 Encoder，GPT 只用 Decoder？

**答**：
- **BERT**（Encoder-only）：双向上下文理解，适合 NLU 任务（分类、NER、QA）。每个 token 能看到左右两侧的信息。
- **GPT**（Decoder-only）：自回归生成，适合 NLG 任务（文本生成、对话）。每个 token 只能看到左侧信息（causal attention）。GPT 用大量数据和参数规模弥补了单向注意力的信息缺失。
- 现在的主流趋势是 **Decoder-only**（GPT、LLaMA、Mistral），因为更统一、更利于 Scaling。

### 面试题 8：说说 Pre-Norm 和 Post-Norm 的区别？

**答**：
- **Post-Norm**（原始论文）：`LayerNorm(x + Sublayer(x))`。残差路径未经归一化，深层时容易出现梯度爆炸/消失，训练不稳定。
- **Pre-Norm**（现代主流）：`x + Sublayer(LayerNorm(x))`。对输入先归一化，残差路径保持恒等映射，训练更稳定，收敛更快。几乎所有现代 LLM（GPT、LLaMA、BERT 后期）都使用 Pre-Norm。

### 面试题 9：Self-Attention 的计算复杂度是多少？怎么优化？

**答**：Self-Attention 的复杂度是 **O(n²·d)**，其中 n 是序列长度，d 是 hidden size。因为 Q·Kᵀ 计算得到一个 n×n 的注意力矩阵。

优化方向：
1. **稀疏 Attention**（Longformer、BigBird）：只计算局部 + 部分全局的注意力
2. **Linear Attention**（Performer）：用核方法将 O(n²) 降到 O(n)
3. **FlashAttention**：通过分块计算 + 不存大矩阵，内存 O(n) 但计算仍 O(n²)，但实际 wall time 快 2-4 倍
4. **KV Cache**：推理时缓存 K、V，避免重复计算

### 面试题 10：手撕 Attention 代码

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class SelfAttention(nn.Module):
    def __init__(self, d_model, num_heads, dropout=0.1):
        super().__init__()
        assert d_model % num_heads == 0
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.W_Q = nn.Linear(d_model, d_model)
        self.W_K = nn.Linear(d_model, d_model)
        self.W_V = nn.Linear(d_model, d_model)
        self.W_O = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x, mask=None):
        batch_size = x.size(0)
        
        # 1. 线性变换 + 分头
        Q = self.W_Q(x).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_K(x).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_V(x).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        
        # 2. Scaled Dot-Product Attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))
        
        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)
        
        output = torch.matmul(attn, V)
        
        # 3. 合并多头
        output = output.transpose(1, 2).contiguous().view(batch_size, -1, self.d_model)
        
        # 4. 输出投影
        return self.W_O(output)
```

---

## 9. 进阶阅读

- [The Illustrated Transformer](http://jalammar.github.io/illustrated-transformer/) — 最直观的图解
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — 原始论文
- [Annotated Transformer](http://nlp.seas.harvard.edu/2018/04/03/attention.html) — 带代码的详细注释
- [LLaMA: Open and Efficient Foundation Language Models](https://arxiv.org/abs/2302.13971) — 现代 Transformer 实现参考
- [FlashAttention: Fast and Memory-Efficient Exact Attention](https://arxiv.org/abs/2205.14135) — 工程优化前沿
