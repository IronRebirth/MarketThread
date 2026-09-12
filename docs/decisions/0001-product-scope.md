# ADR 0001: MarketThread Product Scope

## Status

Accepted

## Date

2026-09-13

## Context

MarketThread is intended to be a production-oriented financial intelligence and research platform.

The product needs to combine:

- global events
- financial news
- market data
- company information
- analytics
- machine learning
- risk analysis
- portfolio context
- explainable AI

A simple stock-prediction dashboard would not provide enough context or explainability for the intended product.

The system must also remain useful when there is insufficient evidence to produce a meaningful signal.

## Decision

MarketThread will be designed as a financial intelligence and decision-support platform.

The core workflow will be:

```text
World Event
    ↓
Information
    ↓
Event
    ↓
Market Impact
    ↓
Company Impact
    ↓
Evidence
    ↓
Signal
    ↓
Risk + Confidence
    ↓
Research Insight