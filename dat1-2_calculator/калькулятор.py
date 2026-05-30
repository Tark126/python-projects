def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        return "Ошибка: деление на ноль!"
    return a / b

operations = {
    "1": add,
    "2": subtract,
    "3": multiply,
    "4": divide
}

print("Добро пожаловать в калькулятор! Введите 'q' в любом поле для выхода.")

while True:
    try:
        # Ввод первого числа
        num1_input = input("Введите первое число: ").strip()
        if num1_input.lower() == 'q':
            print("Выход из программы.")
            break
        num1 = float(num1_input)

        # Ввод второго числа
        num2_input = input("Введите второе число: ").strip()
        if num2_input.lower() == 'q':
            print("Выход из программы.")
            break
        num2 = float(num2_input)

        # Меню операций
        print("\nВыберите операцию:")
        print("1. Сложение (+)")
        print("2. Вычитание (-)")
        print("3. Умножение (*)")
        print("4. Деление (/)")
        print("'q' для выхода")

        operation = input("Ваш выбор: ").strip()

        if operation.lower() == 'q':
            print("Выход из программы.")
            break

        # Проверка корректности операции
        if operation not in operations:
            print("Ошибка: выберите операцию из списка (1/2/3/4).")
            continue

        # Выполнение операции
        result = operations[operation](num1, num2)
        print(f"Результат: {result}\n")

    except ValueError:
        print("Ошибка: введите корректное число!\n")
    except KeyboardInterrupt:
        print("\nВыход из программы (прерывание).")
        break
    except Exception as e:
        print(f"Неизвестная ошибка: {e}\n")
