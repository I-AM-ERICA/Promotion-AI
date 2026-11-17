# 외부 구성요소

- 배경 제거: [rembg](https://github.com/danielgatis/rembg), MIT. 모델은 명시적으로 `u2net`을 지정합니다. 라이브러리 기본 모델을 사용하지 않습니다.
- U2Net: [공식 구현 및 라이선스](https://github.com/xuebinqin/U-2-Net), Apache-2.0. ONNX 가중치는 rembg의 공식 릴리스에서 처음 한 번 내려받으며 저장소에 포함하지 않습니다. 모델 재학습은 없습니다.

상품 사진의 배경 분리는 로컬에서 수행합니다. 상품 사진을 외부 배경 제거 서비스로 보내지 않습니다. 별도로 올린 스타일 참고 이미지는 CLOVA Studio의 HCX-005에 전달됩니다.
