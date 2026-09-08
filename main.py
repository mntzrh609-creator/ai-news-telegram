name: Telegram Bot Test

on:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: تحميل الملفات
        uses: actions/checkout@v4

      - name: إعداد Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: تثبيت المكتبات
        run: pip install -r requirements.txt

      - name: تشغيل اختبار التليغرام
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        run: python main.py
