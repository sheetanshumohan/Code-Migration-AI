"""
Enterprise Modernization & Framework Migration Recipes
Provides rules, transformation prompts, and AST patterns for automated framework migrations.
"""



class MigrationRecipe:
    def __init__(
        self,
        recipe_id: str,
        name: str,
        source_framework: str,
        target_framework: str,
        system_instruction: str,
        required_dependencies: list[str],
    ) -> None:
        self.recipe_id = recipe_id
        self.name = name
        self.source_framework = source_framework
        self.target_framework = target_framework
        self.system_instruction = system_instruction
        self.required_dependencies = required_dependencies


RECIPES: dict[str, MigrationRecipe] = {
    "flask_to_fastapi": MigrationRecipe(
        recipe_id="flask_to_fastapi",
        name="Flask to FastAPI Migration",
        source_framework="Flask (Synchronous)",
        target_framework="FastAPI (Python 3.13 Asynchronous)",
        system_instruction="""
Convert synchronous Flask routes (`@app.route(...)`) to asynchronous FastAPI endpoints (`@app.get(...)`, `@app.post(...)`).
Replace `request.json` with strongly-typed Pydantic v2 schemas (`class RequestModel(BaseModel)`).
Use `Depends()` for database sessions and dependency injection.
Ensure all endpoint functions are `async def`.
Add type annotations to all parameters and responses.
        """,
        required_dependencies=["fastapi>=0.115.0", "pydantic>=2.10.0", "uvicorn>=0.34.0"],
    ),
    "sqlalchemy1_to_sqlalchemy2": MigrationRecipe(
        recipe_id="sqlalchemy1_to_sqlalchemy2",
        name="SQLAlchemy 1.4 to 2.0 Async Upgrade",
        source_framework="SQLAlchemy 1.3 / 1.4",
        target_framework="SQLAlchemy 2.0 Async",
        system_instruction="""
Upgrade models from `Column(Integer)` to `Mapped[int] = mapped_column(...)` using `DeclarativeBase`.
Replace `session.query(Model).filter(...)` with `await session.execute(select(Model).where(...))`.
Ensure all database execution methods use `AsyncSession`.
        """,
        required_dependencies=["sqlalchemy>=2.0.36", "asyncpg>=0.30.0"],
    ),
    "react_class_to_hooks": MigrationRecipe(
        recipe_id="react_class_to_hooks",
        name="React Class Components to React 19 Hooks",
        source_framework="React Class Components (CRA)",
        target_framework="React 19 Functional Components + Hooks (Vite)",
        system_instruction="""
Convert `class MyComponent extends React.Component` to `export default function MyComponent(props)`.
Replace `this.state` and `this.setState` with `useState()`.
Replace lifecycle methods (`componentDidMount`, `componentDidUpdate`, `componentWillUnmount`) with `useEffect()`.
Remove `this.` references.
        """,
        required_dependencies=["react@^19.0.0", "react-dom@^19.0.0", "vite@^6.1.0"],
    ),
    "spring2_to_spring3": MigrationRecipe(
        recipe_id="spring2_to_spring3",
        name="Spring Boot 2.x to Spring Boot 3.x / Java 21",
        source_framework="Spring Boot 2.7 (Java 8/11)",
        target_framework="Spring Boot 3.4 (Java 21)",
        system_instruction="""
Replace all `javax.*` imports with `jakarta.*` (e.g. `jakarta.persistence.*`, `jakarta.servlet.*`).
Upgrade security configurations from deprecated `WebSecurityConfigurerAdapter` to `SecurityFilterChain` bean.
Leverage Java 21 Records and pattern matching where applicable.
        """,
        required_dependencies=["org.springframework.boot:spring-boot-starter-web:3.4.0"],
    ),
    "python2_to_python3": MigrationRecipe(
        recipe_id="python2_to_python3",
        name="Python 2 to Python 3 Migration",
        source_framework="Python 2.7",
        target_framework="Python 3.13",
        system_instruction="""
Convert `print "message"` to `print("message")`.
Convert `except Exception, e:` to `except Exception as e:`.
Update `urllib2` to `urllib.request`.
Ensure string literals are properly handled (unicode prefix u"" is no longer strictly necessary but handled differently).
Replace `xrange()` with `range()`.
        """,
        required_dependencies=[],
    ),
}


class MigrationRecipeManager:
    @staticmethod
    def get_recipe(recipe_id: str) -> MigrationRecipe:
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            return RECIPES["flask_to_fastapi"]
        return recipe

    @staticmethod
    def list_recipes() -> list[dict[str, str]]:
        return [
            {
                "recipe_id": r.recipe_id,
                "name": r.name,
                "source": r.source_framework,
                "target": r.target_framework,
            }
            for r in RECIPES.values()
        ]


recipe_manager = MigrationRecipeManager()
