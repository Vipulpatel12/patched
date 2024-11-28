from patchwork.common.utils.utils import open_with_chardet
from patchwork.step import Step
from patchwork.steps.ReadFile.typed import ReadFileInputs


class ReadFile(Step):
    def __init__(self, inputs):
        """Initializes an instance of the class, ensuring that all required input keys are provided.
        
        Args:
            inputs (dict): A dictionary containing input parameters, including a 'file_path' key.
        
        Raises:
            ValueError: If any required keys are missing from the input dictionary.
        
        Returns:
            None
        """
        super().__init__(inputs)
        missing_keys = ReadFileInputs.__required_keys__.difference(inputs.keys())
        if len(missing_keys) > 0:
            raise ValueError(f"Missing required data: {missing_keys}")

        self.file = inputs["file_path"]

    def run(self):
        """Reads the contents of a specified file and returns its file path along with the content.
        
        Args:
            self: The instance of the class from which this method is called.
        
        Returns:
            dict: A dictionary containing the file path and its contents.
        """ 
        with open_with_chardet(self.file, "r") as f:
            file_contents = f.read()

        return dict(file_path=self.file, file_content=file_contents)
