import pytest
from pytest import FixtureRequest

from bocoel import (
    ComposedCorpus,
    Corpus,
    DataFrameStorage,
    SBertEmbedder,
    WhiteningIndex,
)
from tests import utils

from .indices import test_whitening
from .storages import test_df_storage


def corpus(device: str) -> Corpus:
    storage = DataFrameStorage(test_df_storage.df())
    embedder = SBertEmbedder(device=device)

    return ComposedCorpus.index_storage(
        storage=storage,
        embedder=embedder,
        key="question",
        klass=WhiteningIndex,
        index_kwargs=test_whitening.whiten_kwargs(),
    )


@pytest.fixture
def corpus_fix(request: FixtureRequest) -> Corpus:
    return corpus(device=request.param)


@pytest.mark.parametrize("corpus_fix", utils.torch_devices(), indirect=True)
def test_init_corpus(corpus_fix: Corpus) -> None:
    _ = corpus_fix
