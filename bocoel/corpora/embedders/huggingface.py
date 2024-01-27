from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from bocoel.corpora.embedders.interfaces import Embedder


class HuggingfaceEmbedder(Embedder):
    def __init__(
        self,
        path: str,
        device: str = "cpu",
        batch_size: int = 64,
        transform: Callable[[Any], Tensor] = lambda output: output.logits,
    ) -> None:
        self._model = AutoModelForSequenceClassification.from_pretrained(path)
        self._tokenizer = AutoTokenizer.from_pretrained(path)
        self._batch_size = batch_size

        self._device = device
        self._model = self._model.to(device)
        self._transform = transform

    @property
    def batch(self) -> int:
        return self._batch_size

    @property
    def dims(self) -> int:
        # FIXME: Figure out if all the sequence classification has logits shape 2.
        return 2

    @torch.no_grad()
    def _encode(self, texts: Sequence[str]) -> NDArray:
        encoded = self._tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            max_length=self._tokenizer.model_max_length,
        ).to(self._device)
        output = self._model(**encoded)

        transformed = self._transform(output).cpu().numpy()
        return transformed
