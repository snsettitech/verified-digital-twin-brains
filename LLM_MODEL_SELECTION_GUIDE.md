# LLM Model Selection Guide for Query Rewriting

## Overview

This guide helps you select the optimal LLM model for conversational query rewriting based on your quality, latency, and cost requirements.

---

## Available Models (Latest as of Feb 2026)

### 1. **GPT-4o** (Recommended for Quality) ⭐
```bash
QUERY_REWRITING_MODEL=gpt-4o
```

| Metric | Value |
|--------|-------|
| **Quality** | Excellent - Best understanding of context and nuance |
| **Latency** | ~150-300ms |
| **Cost** | ~$5 per 1M tokens (input) |
| **Best For** | Production deployments prioritizing quality |

**Pros:**
- Best rewrite quality
- Excellent at resolving complex pronouns
- Better intent classification
- Handles edge cases well

**Cons:**
- 2x more expensive than mini
- Slightly higher latency

---

### 2. **GPT-4o-mini** (Recommended for Cost/Speed)
```bash
QUERY_REWRITING_MODEL=gpt-4o-mini
```

| Metric | Value |
|--------|-------|
| **Quality** | Very Good - Sufficient for most use cases |
| **Latency** | ~80-150ms |
| **Cost** | ~$0.15 per 1M tokens (input) |
| **Best For** | High-volume production, cost-sensitive deployments |

**Pros:**
- 30x cheaper than GPT-4o
- 2x faster
- Good enough for 90% of queries
- Ideal for caching scenarios

**Cons:**
- May miss subtle context
- Slightly lower confidence scores

---

### 3. **o1-preview** (NOT Recommended)
```bash
QUERY_REWRITING_MODEL=o1-preview
```

| Metric | Value |
|--------|-------|
| **Quality** | Overkill for query rewriting |
| **Latency** | ~1-3 seconds |
| **Cost** | ~$15 per 1M tokens |
| **Best For** | NOT recommended for query rewriting |

**Why Skip:**
- Too slow for real-time query rewriting
- Overkill for the task
- Expensive
- Reasoning capabilities not needed

---

### 4. **o1-mini** (NOT Recommended)
```bash
QUERY_REWRITING_MODEL=o1-mini
```

| Metric | Value |
|--------|-------|
| **Quality** | Good but slow |
| **Latency** | ~500ms-1s |
| **Cost** | ~$3 per 1M tokens |
| **Best For** | NOT recommended for query rewriting |

**Why Skip:**
- Still slower than GPT-4o
- No significant quality improvement for this task
- More expensive than mini

---

## Model Comparison Matrix

| Model | Quality | Speed | Cost | Recommendation |
|-------|---------|-------|------|----------------|
| **gpt-4o** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 🥇 Best Overall |
| **gpt-4o-mini** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 🥈 Best Value |
| **o1-preview** | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ❌ Not Recommended |
| **o1-mini** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ❌ Not Recommended |

---

## Our Recommendations

### For Production (High Volume)
```bash
QUERY_REWRITING_MODEL=gpt-4o-mini
QUERY_REWRITE_CACHE_ENABLED=true
```
- Use caching to reduce API calls
- 90% of queries work great with mini
- Cost-effective at scale

### For Premium Quality
```bash
QUERY_REWRITING_MODEL=gpt-4o
QUERY_REWRITING_MIN_CONFIDENCE=0.75
```
- Best possible rewrite quality
- Use for enterprise deployments
- Worth the extra cost for critical applications

### For Testing/Development
```bash
QUERY_REWRITING_MODEL=gpt-4o-mini
```
- Cheaper for testing
- Fast iteration
- Switch to gpt-4o for production

---

## Cost Estimates

### Scenario: 100,000 queries/month

**With GPT-4o:**
- Average tokens per query: ~500
- Cost: 100,000 × 500 × $5 / 1M = **$250/month**

**With GPT-4o-mini:**
- Average tokens per query: ~500
- Cost: 100,000 × 500 × $0.15 / 1M = **$7.50/month**

**With Caching (50% hit rate):**
- GPT-4o-mini: **$3.75/month**

---

## Latency Expectations

### End-to-End Query Rewriting Latency

| Model | P50 | P95 | P99 |
|-------|-----|-----|-----|
| **gpt-4o-mini** | 100ms | 180ms | 250ms |
| **gpt-4o** | 200ms | 350ms | 500ms |
| **With cache hit** | 5ms | 10ms | 20ms |

---

## Configuration Examples

### High-Performance Production
```bash
QUERY_REWRITING_ENABLED=true
QUERY_REWRITING_MODEL=gpt-4o
QUERY_REWRITE_CACHE_ENABLED=true
QUERY_REWRITE_CACHE_SIZE=2000
QUERY_REWRITING_TIMEOUT=2.0
```

### Cost-Optimized Production
```bash
QUERY_REWRITING_ENABLED=true
QUERY_REWRITING_MODEL=gpt-4o-mini
QUERY_REWRITE_CACHE_ENABLED=true
QUERY_REWRITE_CACHE_SIZE=5000
QUERY_REWRITING_TIMEOUT=1.5
```

### Premium Quality
```bash
QUERY_REWRITING_ENABLED=true
QUERY_REWRITING_MODEL=gpt-4o
QUERY_REWRITE_CACHE_ENABLED=false  # Always fresh rewrites
QUERY_REWRITING_MIN_CONFIDENCE=0.8
QUERY_REWRITING_TIMEOUT=5.0
```

---

## About GPT-5

**Important:** As of February 2026, **GPT-5 has not been released** by OpenAI. The latest available models are:
- GPT-4o (flagship)
- GPT-4o-mini (cost-effective)
- o1 series (reasoning models)

When GPT-5 is released:
1. We'll evaluate it for query rewriting
2. Update this guide
3. Consider switching if it offers better quality/speed ratio

---

## Testing Model Performance

Run the evaluation to compare models:

```bash
cd backend

# Test with gpt-4o-mini
QUERY_REWRITING_MODEL=gpt-4o-mini python -m modules.query_rewrite_evaluator

# Test with gpt-4o
QUERY_REWRITING_MODEL=gpt-4o python -m modules.query_rewrite_evaluator

# Compare results
cat query_rewrite_eval_results.json
```

---

## Migration Guide

### Switching from mini to 4o
```bash
# 1. Update environment variable
QUERY_REWRITING_MODEL=gpt-4o

# 2. Monitor for 24 hours
# Watch metrics: latency, cost, quality scores

# 3. Adjust confidence threshold if needed
QUERY_REWRITING_MIN_CONFIDENCE=0.75
```

### Switching from 4o to mini
```bash
# 1. Update environment variable
QUERY_REWRITING_MODEL=gpt-4o-mini

# 2. Enable caching to compensate
QUERY_REWRITE_CACHE_ENABLED=true
QUERY_REWRITE_CACHE_SIZE=5000

# 3. Monitor pass rate on evaluation
```

---

## Quick Decision Tree

```
Is cost a major concern?
├── YES → Use gpt-4o-mini + caching
└── NO → Continue...
    
    Is maximum quality required?
    ├── YES → Use gpt-4o
    └── NO → Use gpt-4o-mini
```

---

## Summary

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| **Default Production** | `gpt-4o` | Best balance of quality and speed |
| **High Volume** | `gpt-4o-mini` | 30x cheaper, good enough |
| **Enterprise/Premium** | `gpt-4o` | Maximum quality |
| **Testing** | `gpt-4o-mini` | Cost-effective |
| **Latency Critical** | `gpt-4o-mini` + cache | Fastest option |

---

**Last Updated:** 2026-02-20  
**Latest Model:** GPT-4o (Feb 2026)
