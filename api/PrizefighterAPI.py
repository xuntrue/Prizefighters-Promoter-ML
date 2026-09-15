from api.Weight_Classes import WeightClasses, WeightClassError

class PrizefighterAPI:
    """Single entry point the UI layer talks to."""

    def __init__(self):
        self.weight_classes = WeightClasses()

    # --- Weight_Classes ---
    def get_weight_classes(self):
        return self.weight_classes.get_all()

    def add_weight_class(self, weight_limit: int, weight_class: str):
        self.weight_classes.add(weight_limit, weight_class)

    def update_weight_class(self, old_weight_limit: int, new_weight_limit: int, new_weight_class: str):
        self.weight_classes.update(old_weight_limit, new_weight_limit, new_weight_class)

    def delete_weight_class(self, weight_limit: int):
        self.weight_classes.delete(weight_limit)
