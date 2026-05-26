# 跨会话持久信息

from pydantic import Field, BaseModel


class Reservation(BaseModel):
    """预订信息"""

    order_id: str = Field(..., description="订单id")
    house_name: str = Field(..., description="房源名称")
    phone_number: str = Field(..., description="房源预订电话")
    price: float = Field(default=None, description="价格，单位：元/月")
    house_description: str | None = Field(default=None, description="房源详细信息")
    city: str = Field(default=None, description="房子所在城市")
    area: str = Field(default=None, description="房子所在区县")

class UserPreference(BaseModel):
    """用户偏好"""

    budget_min: float = Field(default=0.00, description="用户预算下限")
    budget_max: float = Field(default=10000.00, description="用户预算上限")
    reservations: list[Reservation]
