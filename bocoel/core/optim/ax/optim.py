from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from ax.modelbridge import ModelBridge, cross_validation
from ax.modelbridge.generation_strategy import GenerationStep, GenerationStrategy
from ax.plot import contour, diagnostic, scatter, slice
from ax.service.ax_client import AxClient, ObjectiveProperties
from ax.utils.notebook import plotting
from typing_extensions import Self

from bocoel.core.optim import utils as optim_utils
from bocoel.core.optim.interfaces import Optimizer, State
from bocoel.core.optim.utils import RemainingSteps
from bocoel.corpora import Corpus, Index, SearchResult
from bocoel.models import Evaluator

from . import types, utils
from .types import AxServiceParameter
from .utils import GenStepDict

_KEY = "entropy"


class AxServiceOptimizer(Optimizer):
    """
    The Ax optimizer that uses the service API.
    See https://ax.dev/tutorials/gpei_hartmann_service.html
    """

    def __init__(
        self,
        index: Index,
        evaluate_fn: Callable[[SearchResult], float],
        steps: Sequence[GenStepDict | GenerationStep],
        minimize: bool = True,
    ) -> None:
        gen_steps = [utils.generation_step(step) for step in steps]
        gen_strat = GenerationStrategy(steps=gen_steps)

        self._ax_client = AxClient(generation_strategy=gen_strat)
        self._create_experiment(index, minimize=minimize)
        self._remaining_steps = RemainingSteps(self._terminate_step(gen_steps))

        self._index = index
        self._evaluate_fn = evaluate_fn

    @property
    def terminate(self) -> bool:
        return self._remaining_steps.done

    def step(self) -> State:
        self._remaining_steps.step()

        # FIXME: Currently only supports 1 item evaluation (in the form of float).
        parameters, trial_index = self._ax_client.get_next_trial()
        state = self._evaluate(parameters)
        self._ax_client.complete_trial(
            trial_index, raw_data={_KEY: float(state.evaluation)}
        )
        return state

    def render(self, kind: str, **kwargs: Any) -> None:
        """
        See https://ax.dev/tutorials/visualizations.html for details.
        """

        func: Callable

        match kind:
            case "interactive":
                func = self._render_interactive
            case "static":
                func = self._render_static
            case "tradeoff":
                func = self._render_tradeoff
            case "cross_validate" | "cv":
                func = self._render_cross_validate
            case "slice":
                func = self._render_slice
            case "tile":
                func = self._render_tile
            case _:
                raise ValueError("Not supported")

        func(**kwargs)

    def _create_experiment(self, index: Index, minimize: bool) -> None:
        self._ax_client.create_experiment(
            parameters=types.parameter_configs(index),
            objectives={_KEY: ObjectiveProperties(minimize=minimize)},
        )

    def _evaluate(self, parameters: dict[str, AxServiceParameter]) -> State:
        index_dims = self._index.dims
        names = types.parameter_name_list(index_dims)
        query = np.array([parameters[name] for name in names])

        return optim_utils.evaluate_index(
            query=query, index=self._index, evaluate_fn=self._evaluate_fn
        )

    @classmethod
    def from_index(
        cls,
        index: Index,
        evaluate_fn: Callable[[SearchResult], float],
        **kwargs: Any,
    ) -> Self:
        return cls(index=index, evaluate_fn=evaluate_fn, **kwargs)

    @classmethod
    def from_steps(
        cls,
        corpus: Corpus,
        evaluator: Evaluator,
        **kwargs: Any,
    ) -> Self:
        return cls.evaluate_corpus(corpus=corpus, evaluator=evaluator, **kwargs)

    @staticmethod
    def _terminate_step(steps: list[GenerationStep]) -> int:
        trials = [step.num_trials for step in steps]
        if all(t >= 0 for t in trials):
            return sum(trials)
        else:
            return -1

    @property
    def _gen_strat_model(self) -> ModelBridge:
        model = self._ax_client.generation_strategy.model
        assert model is not None
        return model

    def _render_static(self, param_x: str, param_y: str) -> None:
        plotting.render(
            self._ax_client.get_contour_plot(
                param_x=param_x, param_y=param_y, metric_name=_KEY
            )
        )

    def _render_interactive(self) -> None:
        plotting.render(
            contour.interact_contour(model=self._gen_strat_model, metric_name=_KEY)
        )

    def _render_tradeoff(self) -> None:
        plotting.render(
            scatter.plot_objective_vs_constraints(
                model=self._gen_strat_model, objective=_KEY, rel=False
            )
        )

    def _render_cross_validate(self) -> None:
        plotting.render(
            diagnostic.interact_cross_validation(
                cv_results=cross_validation.cross_validate(self._gen_strat_model)
            )
        )

    def _render_slice(self, param_name: str) -> None:
        plotting.render(
            slice.plot_slice(
                model=self._gen_strat_model,
                param_name=param_name,
                metric_name=_KEY,
            )
        )

    def _render_tile(self) -> None:
        plotting.render(scatter.interact_fitted(model=self._gen_strat_model, rel=False))
