"""
Unit Tests for Framework Migration Recipes
"""

from app.domain.migration.recipes import recipe_manager


def test_recipe_retrieval():
    """Verify built-in modernization recipes are registered and configured."""
    recipes = recipe_manager.list_recipes()
    assert len(recipes) >= 4

    flask_recipe = recipe_manager.get_recipe("flask_to_fastapi")
    assert flask_recipe.target_framework.startswith("FastAPI")
    assert any("fastapi" in dep for dep in flask_recipe.required_dependencies)

    react_recipe = recipe_manager.get_recipe("react_class_to_hooks")
    assert "React 19" in react_recipe.target_framework
