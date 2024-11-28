import importlib
import textwrap

from typing_extensions import (
    Annotated,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypedDict,
    get_args,
    get_origin,
    get_type_hints,
)

from patchwork.step import Step


class StepTypeConfig(object):
    def __init__(
        self,
        is_config: bool = False,
        is_path: bool = False,
        and_op: List[str] = None,
        or_op: List[str] = None,
        xor_op: List[str] = None,
        msg: str = "",
    ):
        """Initializes a new instance of the class.
        
        Args:
            is_config (bool): Indicates whether the instance is a configuration object. Defaults to False.
            is_path (bool): Indicates whether the instance represents a path. Defaults to False.
            and_op (List[str]): A list of strings representing AND operations. Defaults to an empty list if None.
            or_op (List[str]): A list of strings representing OR operations. Defaults to an empty list if None.
            xor_op (List[str]): A list of strings representing XOR operations. Defaults to an empty list if None.
            msg (str): A message associated with the instance. Defaults to an empty string.
        
        Returns:
            None: This constructor does not return a value.
        self.is_config = is_config
        self.is_path: bool = is_path
        self.and_op: List[str] = and_op or []
        self.or_op: List[str] = or_op or []
        self.xor_op: List[str] = xor_op or []
        self.msg: str = msg


def validate_steps_with_inputs(keys: Iterable[str], *steps: Type[Step]) -> None:
    """Validates a series of steps against a set of input keys and reports any errors found.
    
    Args:
        keys Iterable[str]: A collection of keys to validate against the steps.
        *steps Type[Step]: A variable number of step classes to validate using the provided keys.
    
    Returns:
        None: Raises a ValueError if any of the validation steps produce errors.
    """
    current_keys = set(keys)
    report = {}
    for step in steps:
        output_keys, step_report = validate_step_with_inputs(current_keys, step)
        current_keys = current_keys.union(output_keys)
        report[step.__name__] = step_report

    has_error = any(len(value) > 0 for value in report.values())
    if not has_error:
        return

    error_message = "Invalid inputs for steps:\n"
    for step_name, step_report in sorted(report.items(), key=lambda x: x[0]):
        if len(step_report) > 0:
            error_message += f"Step: {step_name}\n"
            for key, msg in step_report.items():
                error_message += f"  - {key}: \n{textwrap.indent(msg, '      ')}\n"
    raise ValueError(error_message)


__NOT_GIVEN = TypedDict


def validate_step_type_config_with_inputs(
    key_name: str, input_keys: Set[str], step_type_config: StepTypeConfig
) -> Tuple[bool, str]:
    """Validates the configuration of a step type based on input keys and the specified constraints in the step type configuration.
    
    Args:
        key_name (str): The key name to validate against the input keys.
        input_keys (Set[str]): A set of input keys provided for validation.
        step_type_config (StepTypeConfig): The configuration object that defines validation rules (and_op, or_op, xor_op) and associated messages.
    
    Returns:
        Tuple[bool, str]: A tuple containing a boolean indicating the validation result and a message providing details about any validation failures or the configured message.
    """
    is_key_set = key_name in input_keys

    and_keys = set(step_type_config.and_op)
    if len(and_keys) > 0:
        missing_and_keys = sorted(and_keys.difference(input_keys))
        if is_key_set and len(missing_and_keys) > 0:
            return (
                False,
                step_type_config.msg
                or f"Missing required input data because {key_name} is set: {', '.join(missing_and_keys)}",
            )

    or_keys = set(step_type_config.or_op)
    if len(or_keys) > 0:
        missing_or_keys = or_keys.difference(input_keys)
        if not is_key_set and len(missing_or_keys) == len(or_keys):
            return (
                False,
                step_type_config.msg
                or f"Missing required input: At least one of {', '.join(sorted([key_name, *or_keys]))} has to be set",
            )

    xor_keys = set(step_type_config.xor_op)
    if len(xor_keys) > 0:
        missing_xor_keys = xor_keys.difference(input_keys)
        if not is_key_set and len(missing_xor_keys) == len(xor_keys):
            return (
                False,
                step_type_config.msg or f"Missing required input: Exactly one of {', '.join(xor_keys)} has to be set",
            )
        elif is_key_set and len(missing_xor_keys) < len(xor_keys) - 1:
            conflicting_keys = xor_keys.intersection(input_keys)
            return (
                False,
                step_type_config.msg
                or f"Excess input data: {', '.join(sorted(conflicting_keys))} cannot be set at the same time",
            )

    return True, step_type_config.msg


def validate_step_with_inputs(input_keys: Set[str], step: Type[Step]) -> Tuple[Set[str], Dict[str, str]]:
    """Validates the input keys against the expected input model of a given step and generates a report of missing or mismatched inputs.
    
    Args:
        input_keys Set[str]: A set of keys provided as input for validation.
        step Type[Step]: The step class that contains expected input and output models.
    
    Returns:
        Tuple[Set[str], Dict[str, str]]: A tuple containing a set of required output keys and a dictionary reporting any validation issues with input keys.
    """
    module_path, _, _ = step.__module__.rpartition(".")
    step_name = step.__name__
    type_module = importlib.import_module(f"{module_path}.typed")
    step_input_model = getattr(type_module, f"{step_name}Inputs", __NOT_GIVEN)
    step_output_model = getattr(type_module, f"{step_name}Outputs", __NOT_GIVEN)
    if step_input_model is __NOT_GIVEN:
        raise ValueError(f"Missing input model for step {step_name}")
    if step_output_model is __NOT_GIVEN:
        raise ValueError(f"Missing output model for step {step_name}")

    step_report = {}
    for key in step_input_model.__required_keys__:
        if key not in input_keys:
            step_report[key] = f"Missing required input data"
            continue

    step_type_hints = get_type_hints(step_input_model, include_extras=True)
    for key, field_info in step_type_hints.items():
        step_type_config = find_step_type_config(field_info)
        if step_type_config is None:
            continue

        if key in step_report.keys():
            step_report[key] = step_type_config.msg or f"Missing required input data"
            continue

        is_ok, msg = validate_step_type_config_with_inputs(key, input_keys, step_type_config)
        if not is_ok:
            step_report[key] = msg

    return set(step_output_model.__required_keys__), step_report


def find_step_type_config(python_type: type) -> Optional[StepTypeConfig]:
    """Finds the configuration associated with a specific step type based on the provided Python type.
    
    Args:
        python_type type: The Python type for which to find the step type configuration.
    
    Returns:
        Optional[StepTypeConfig]: The configuration for the step type if found, otherwise None.
    """
    annotated = find_annotated(python_type)
    if annotated is None:
        return None
    for metadata in annotated.__metadata__:
        if metadata.__class__.__name__ == StepTypeConfig.__name__:
            return metadata

    return None


def find_annotated(python_type: Type) -> Optional[Type[Annotated]]:
    """Recursively searches for the first occurrence of an Annotated type 
    within the provided Python type. If the given type is an Annotated type, 
    it returns the type itself. If there are type arguments, it checks 
    each argument for an Annotated type until one is found.
    
    Args:
        python_type Type: The type to search for Annotated types.
    
    Returns:
        Optional[Type[Annotated]]: The found Annotated type or None 
        if no Annotated type is found.
    """
    origin = get_origin(python_type)
    args = get_args(python_type)
    if origin is Annotated:
        return python_type

    if len(args) > 0:
        for arg in args:
            possible_step_type_config = find_annotated(arg)
            if possible_step_type_config is not None:
                return possible_step_type_config

    return None
