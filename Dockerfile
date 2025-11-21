FROM python:3.13-slim

# 1. Робоча директорія всередині контейнера
WORKDIR /app

# 2. Копіюємо requirements
COPY requirements.txt .

# 3. Ставимо залежності
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копіюємо весь код
COPY . .

# 5. За замовчуванням — нічого не запускаємо
CMD ["bash"]
