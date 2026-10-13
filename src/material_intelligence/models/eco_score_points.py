from dataclasses import dataclass


@dataclass
class Criterion:
    id: int
    points: int


@dataclass
class ProductConfig:
    product_type: str
    criteria: list[Criterion]

    @property
    def total_max_points(self) -> int:
        return sum(c.points for c in self.criteria)



product_textile = ProductConfig(
    product_type="Textile product",
    criteria=[
        Criterion(1, 40),
        Criterion(2, 40),
        Criterion(3, 30),
        Criterion(4, 60),
        Criterion(5, 20),
        Criterion(6, 50),
        Criterion(7, 40),
        Criterion(8, 40),
        Criterion(9, 60),
        Criterion(10, 20),
        Criterion(11, 40),
        Criterion(12, 20),
        Criterion(13, 10),
        Criterion(14, 30),
        Criterion(15, 10)
    ]
)

product_acoustic = ProductConfig(
    product_type="Acoustic product",
    criteria=[
        Criterion(1, 40),
        Criterion(2, 40),
        Criterion(3, 30),
        Criterion(4, 60),
        Criterion(5, 20),
        Criterion(6, 40),
        Criterion(7, 50),
        Criterion(8, 40),
        Criterion(9, 40),
        Criterion(10, 40),
        Criterion(11, 20),
        Criterion(12, 30),
        Criterion(13, 40),
        Criterion(14, 40),
        Criterion(15, 30),
        Criterion(16, 30),
        Criterion(17, 30)
    ]
)

product_lighting = ProductConfig(
    product_type="Lighting product",
    criteria=[
        Criterion(1, 40),
        Criterion(2, 40),
        Criterion(3, 30),
        Criterion(4, 20),
        Criterion(5, 60),
        Criterion(6, 60),
        Criterion(7, 45),
        Criterion(8, 55),
        Criterion(9, 60),
        Criterion(10, 40),
        Criterion(11, 60),
        Criterion(12, 40),
        Criterion(13, 60)
    ]
)