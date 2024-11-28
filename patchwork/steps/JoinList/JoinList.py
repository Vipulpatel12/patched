import json

from patchwork.step import Step, StepStatus
from patchwork.steps.JoinList.typed import JoinListInputs, JoinListOutputs


class JoinList(Step, input_class=JoinListInputs, output_class=JoinListOutputs):
    def __init__(self, inputs):
        """Initializes an instance of the class, setting up its attributes based on provided inputs.
        
        Args:
            inputs dict: A dictionary containing initialization parameters. 
                Must include a "list" key for list data and a "delimiter" key for separating values.
                Optionally, a "key" can be provided to customize the possible_keys.
        
        Returns:
            None: This constructor does not return a value.
        """
        super().__init__(inputs)

        self.list = inputs["list"]
        self.delimiter = inputs["delimiter"]
        self.possible_keys = ["body", "text"]
        if inputs.get("key") is not None:
            self.possible_keys.insert(0, inputs.get("key"))

    def run(self):
        """Processes a list of items, extracting strings or specific values from dictionaries while converting non-string items to strings.
        
        Args:
            self.list list: The list of items to process, which can contain strings, dictionaries, or other data types.
        
        Returns:
            dict: A dictionary containing a 'text' key with a concatenated string of processed items, separated by a delimiter.
        """
        if len(self.list) == 0:
            self.set_status(StepStatus.SKIPPED, "List is empty")
            return dict()

        items = []
        for item in self.list:
            if isinstance(item, str):
                items.append(item)
            elif isinstance(item, dict):
                is_added = False
                for possible_key in self.possible_keys:
                    if possible_key in item.keys():
                        items.append(item.get(possible_key))
                        is_added = True
                        break
                if not is_added:
                    items.append(json.dumps(item))
            else:
                items.append(str(item))

        return dict(text=self.delimiter.join(items))
