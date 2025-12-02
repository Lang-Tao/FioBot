from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""
    fio_adders: list[int] = [3200054848,
                             1347136323]
