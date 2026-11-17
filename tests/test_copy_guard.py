import pytest
from promotion_assistant.models import Brief, Design, validate_copy
from promotion_assistant.copy_guard import claims


@pytest.fixture
def brief():
    return Brief(store={"store_id":"999","name":"오후의 베이커리"},product="소금빵",
                 price=3500,original_price=4000,period="11월 20일 ~ 11월 27일")


@pytest.mark.parametrize("copy",[
    "3,500원에 만나보세요", "3500 원으로 즐기는 한입", "3천5백원으로 만나요",
    "0.35만원의 행복", "3.5천원에 만나요", "4,000원에서 3,500원으로",
    "12% 할인", "12.5퍼센트 할인", "500원 할인", "11월 20일부터 만나요",
    "가격은 3,500", "３，５００원에 만나요",
])
def test_equivalent_price_and_derived_discount_are_valid(brief,copy):
    validate_copy(Design(template_id="editorial",palette="cream",headline=copy),brief)


@pytest.mark.parametrize("copy",[
    "90% 할인", "13% 할인", "4,000% 할인", "3,500개 증정", "999명 한정",
    "1+1 행사", "무료 체험 0원", "700원 할인", "-3500원", "3500배 더 맛있게",
])
def test_new_claims_still_rejected(brief,copy):
    with pytest.raises(ValueError):
        validate_copy(Design(template_id="editorial",palette="cream",headline=copy),brief)


def test_copied_offer_and_zero_price():
    brief=Brief(store={"store_id":"1","name":"가게"},product="1+1 커피",price=0,message="선착순 10명")
    validate_copy(Design(template_id="editorial",palette="cream",headline="1+1 커피를 0원에",subhead="선착순 10명에게"),brief)
    assert ("offer",(1,1)) in claims("1 + 1")


def test_price_number_does_not_authorize_discount():
    brief=Brief(store={"store_id":"1","name":"가게"},product="상품",price=50)
    with pytest.raises(ValueError):
        validate_copy(Design(template_id="editorial",palette="cream",headline="50% 할인"),brief)
