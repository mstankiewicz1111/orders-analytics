from pydantic import BaseModel


class TableRow(BaseModel):
    id: int
    symbol_kolor: str
    m1_stan_dyspozycyjny: int
    rezerwacje: int


class SyncStatus(BaseModel):
    id: int
    started_at: str | None
    finished_at: str | None
    status: str
    products_found: int
    batches_processed: int
    rows_written_current: int
    rows_written_history: int
    error_message: str | None
