from __future__ import annotations

import contextlib
import functools
from collections import Counter

from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from typing_extensions import Type

from patchwork.logger import console, logger
from patchwork.step import Step


class PatchflowProgressBar:
    __MAX_PROGRESS = 100.00

    def __init__(self, patchflow: Step):
        """Initializes a new instance of the class and sets up a patchflow step with a progress bar.
        
        Args:
            patchflow Step: An instance of the Step class that defines the flow to be executed.
        
        Returns:
            None: This constructor does not return a value.
        """
        self.__step_counter = Counter()
        self.__current_progress = 0.00
        self.__patchflow_name = patchflow.__class__.__name__

        patchflow_run_func = patchflow.run

        def inner_run():
            """Executes the patchflow run function and updates the progress bar upon completion.
            
            Args:
                None
            
            Returns:
                Any: The result of the patchflow run function.
            """
            try:
                return patchflow_run_func()
            finally:
                self.__progress_bar_update(
                    description=f"[bold green]Finished {self.__patchflow_name}", completed=self.__MAX_PROGRESS
                )

        patchflow.run = inner_run

    def register_steps(self, *steps: Type[Step]):
        """Registers multiple steps in the current context.
        
        Args:
            steps Type[Step]: A variable number of Step types to be registered.
        
        Returns:
            None: This method does not return any value.
        """ 
        for step in steps:
            self.register_step(step)

    def register_step(self, step: Type[Step]):
        """Registers a Step instance by wrapping its run method with an update context manager.
        
        Args:
            step Type[Step]: The Step class to be registered.
        
        Returns:
            None: This method does not return any value.
        """
        step_run_func = step.run

        def inner_run(*args, **kwargs):
            """Executes the specified step function while updating the internal state.
            
            Args:
                *args: Variable length argument list to be passed to the step run function.
                **kwargs: Arbitrary keyword arguments to be passed to the step run function.
            
            Returns:
                The return value of the step run function.
            """
            with self.__update(step):
                return step_run_func(*args, **kwargs)

        step.run = inner_run
        self.__step_counter[step] = 0

    @property
    def __remaining_progress(self):
        """Calculates the remaining progress by subtracting the current progress from the maximum progress.
        
        Args:
            None
        
        Returns:
            int: The amount of progress that is still remaining to reach the maximum progress.
        """
        return self.__MAX_PROGRESS - self.__current_progress

    @property
    def __increment_progress(self):
        """Increments the current progress based on remaining progress and step counter metrics.
        
        Args:
            None
        
        Returns:
            float: The increment value added to the current progress.
        """ 
        max_counter = max(self.__step_counter.most_common()[0][1], 1)
        max_section = len(self.__step_counter) * max_counter
        increment = round(self.__remaining_progress / max_section, 2)
        self.__current_progress += increment
        return increment

    @functools.cached_property
    def __progress_bar(self):
        """Constructs and returns a progress bar for tracking task completion.
        
        Args:
            None
        
        Returns:
            Progress: An instance of the Progress class configured with a spinner, default columns, 
                      and a time elapsed column for displaying progress information.
        """
        return Progress(SpinnerColumn(), *Progress.get_default_columns(), TimeElapsedColumn(), console=console)

    @functools.cached_property
    def __progress_bar_update(self):
        """Updates the progress bar with the current task details and prepares a callable to update it further.
        
        Args:
            None
        
        Returns:
            Callable: A partially applied function that updates the progress bar for the current task.
        """
        progress = self.__progress_bar
        logger.register_progress_bar(progress)
        task_id = progress.add_task(
            description=f"[bold green]Running {self.__patchflow_name}",
            total=self.__MAX_PROGRESS,
        )
        return functools.partial(progress.update, task_id, refresh=True)

    @contextlib.contextmanager
    def __update(self, step: type):
        """Updates the progress bar and step counter for a given step.
        
        Args:
            step type: The step class for which the progress is being updated.
        
        Returns:
            None: This method yields control to the caller and does not return a value.
        """
        self.__progress_bar_update(
            description=f"[bold green]Running {step.__name__}",
            advance=self.__increment_progress,
        )
        self.__step_counter[step] += 1
        yield
        return
