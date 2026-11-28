"""Typed build plans: one pydantic model per operation, picked by the "op" field.

Plans are validated against these models before anything is built, so a bad plan fails with
a message that names the operation and the field (e.g. "ops.2 (tree).size: Input should be
'small', 'medium', 'tall', 'fat' or 'big'"). The MCP `build` tool publishes this schema, so a
client can see every field and allowed value up front.
"""
from typing import Annotated, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Colour = Union[int, str]                 # LDraw code or colour name ("dark bluish grey")
Point = Tuple[float, float]              # (x, z) in studs; z = 0 is the front edge
Spin = Literal["N", "E", "S", "W"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Area(_M):
    """Exactly one of rect / ellipse / polygon / cells."""
    rect: Optional[Tuple[int, int, int, int]] = Field(None, description="x0, z0, x1, z1 (x1, z1 exclusive)")
    ellipse: Optional[Tuple[float, float, float, float]] = Field(None, description="cx, cz, rx, rz")
    polygon: Optional[List[Point]] = Field(None, min_length=3)
    cells: Optional[List[Tuple[int, int]]] = None
    rough: float = Field(0.0, ge=0, le=1, description="noisy outline, 0..1")

    @model_validator(mode="after")
    def _one_shape(self):
        n = sum(v is not None for v in (self.rect, self.ellipse, self.polygon, self.cells))
        if n != 1:
            raise ValueError("give exactly one of rect, ellipse, polygon, cells")
        return self


class _Op(_M):
    id: Optional[str] = Field(None, description="name for this op's parts")
    seed: Optional[int] = None


class Brick(_Op):
    op: Literal["brick"]
    part: str
    colour: Optional[Colour] = None
    at: Point
    y: Optional[int] = Field(None, description="plates; default: the surface there")
    spin: Spin = "N"


class Block(_Op):
    op: Literal["block"]
    area: Area
    height: int = Field(3, ge=1, le=60, description="plates")
    colour: Optional[Colour] = None
    top: Literal["tiles", "studs", "grass"] = "tiles"
    top_colour: Optional[Colour] = None
    hollow: bool = True


class Ldraw(_Op):
    op: Literal["ldraw"]
    lines: List[str] = Field(min_length=1)


class Hill(_Op):
    op: Literal["hill"]
    area: Area
    height: int = Field(8, ge=1, le=96, description="plates at the top")
    style: Literal["terraces", "rock"] = "terraces"
    falloff: Optional[float] = Field(None, gt=0, description="studs from edge to full height")
    colour: Optional[Colour] = None
    accent: Optional[Colour] = None
    lean: float = Field(0.8, ge=0, le=2, description="rock only: studs of set-back per brick of height (0 = vertical)")
    accent_amount: float = Field(0.06, ge=0, le=0.8, description="rock only: share of the accent colour")


class Boulder(_Op):
    op: Literal["boulder"]
    at: List[Tuple[int, int, Literal[1, 2, 4, 6]]] = Field(min_length=1, description="[x, z, size]")
    colours: Optional[List[Colour]] = None


Width = Union[float, Tuple[float, float]]


class Path(_Op):
    op: Literal["path"]
    points: List[Point] = Field(min_length=2)
    width: Width = 3
    style: Literal["cobble", "dirt"] = "cobble"


class Water(_Op):
    op: Literal["water"]
    points: Optional[List[Point]] = Field(None, min_length=2, description="a stream")
    area: Optional[Area] = Field(None, description="a pond")
    width: Width = 4
    colour: Optional[Colour] = None

    @model_validator(mode="after")
    def _shape(self):
        if (self.points is None) == (self.area is None):
            raise ValueError("give points (a stream) or area (a pond), not both")
        return self


class Waterfall(_Op):
    op: Literal["waterfall"]
    at: Point = Field(description="min corner [x, z] of the falling water's footprint, in front of the cliff")
    width: int = Field(2, ge=1, le=16, description="studs along x")
    depth: int = Field(1, ge=1, le=8, description="studs along z")
    height: int = Field(24, ge=3, le=96, description="plates from the ground to the top of the fall")
    colour: Optional[Colour] = None
    streak_colour: Optional[Colour] = None


class Tree(_Op):
    op: Literal["tree"]
    kind: Literal["oak", "birch", "pine", "palm", "cypress"] = "oak"
    size: Literal["small", "medium", "tall", "fat", "big"] = "medium"
    at: Point
    leaf: Optional[Union[Colour, List[Colour]]] = None
    bark: Optional[Colour] = None


PlantKind = Literal["tuft", "flower", "flowers", "bush", "big_bush", "fern", "leafy", "reeds",
                    "bamboo", "cactus", "succulent", "stone"]


class Plant(_Op):
    op: Literal["plant"]
    kind: PlantKind = "bush"
    at: Point


class Scatter(_Op):
    op: Literal["scatter"]
    area: Optional[Area] = None
    kinds: List[Union[PlantKind, Literal["tree:oak", "tree:birch", "tree:pine", "tree:palm", "tree:cypress"]]] = \
        ["tuft", "flower", "bush"]
    density: float = Field(0.08, gt=0, le=1)
    keep_clear: List[Area] = []


Op = Annotated[Union[Brick, Block, Ldraw, Hill, Boulder, Path, Water, Waterfall, Tree, Plant, Scatter],
               Field(discriminator="op")]


class Board(_M):
    width: int = Field(32, ge=4, le=192)
    depth: int = Field(32, ge=4, le=192)
    colour: Colour = "green"


class Plan(_M):
    name: str = "brickscape build"
    board: Board = Board()
    seed: int = 1
    ops: List[Op] = []


def parse(plan):
    """dict / JSON string / Plan -> validated plain dict for the compiler. Raises PlanError."""
    from brickscape.plan import PlanError
    try:
        if isinstance(plan, Plan):
            p = plan
        elif isinstance(plan, str):
            p = Plan.model_validate_json(plan)
        else:
            p = Plan.model_validate(plan)
    except ValidationError as e:
        msgs = []
        for err in e.errors()[:8]:
            loc = ".".join(str(x) for x in err["loc"])
            msgs.append(f"{loc}: {err['msg']}")
        raise PlanError("invalid plan:\n  " + "\n  ".join(msgs)) from None
    return p.model_dump(exclude_none=True)
