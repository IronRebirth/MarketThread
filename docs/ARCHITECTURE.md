```markdown
# MarketThread Architecture

## 1. Purpose

This document describes the intended high-level architecture of MarketThread.

The architecture may evolve as implementation proceeds, but changes should be documented when they materially affect the system design.

---

## 2. High-Level Architecture

```text
                         Browser
                            |
                            v
                    Next.js Web Application
                            |
                            v
                       FastAPI API
                            |
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
     PostgreSQL           Redis          Background Workers
                                               |
                            +------------------+------------------+
                            |                  |                  |
                            v                  v                  v
                      News Pipeline      Market Pipeline      ML Pipeline
                            |                  |                  |
                            +------------------+------------------+
                                               |
                                               v
                                      Intelligence Layer
                                               |
                        +------------------+----+------------------+
                        |                  |                       |
                        v                  v                       v
                      Events            Signals                  Risk
                        |                  |                       |
                        +------------------+-----------------------+
                                           |
                                           v
                                  Recommendation Engine
                                           |
                                           v
                                    AI Explanation Layer
                                           |
                                           v
                                         User