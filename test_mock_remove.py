from models import models as mock_models
from models.users_model import remove_item_from_list

mock_models.users = {
    "test@example.com": {
        "lists": [
            {
                "id": "list1",
                "items": [{"name": "Milk"}, "Bread"]
            }
        ]
    }
}

res = remove_item_from_list("test@example.com", "list1", "Milk")
print("Removed Milk?", res)

res = remove_item_from_list("test@example.com", "list1", "Bread")
print("Removed Bread?", res)
