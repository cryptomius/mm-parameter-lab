"""mm_sim — market-maker simulator core.

The simulator is event-driven: a market-data generator produces mid-price ticks,
noise and informed traders post orders into an L2 book, and an Avellaneda-Stoikov
quoter sits on top managing inventory. Every metric the findings document needs
is computed online and persisted to parquet.
"""

__version__ = "0.1.0"
