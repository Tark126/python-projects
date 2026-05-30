r_name = input("как тебя зовут?:")
c_name = r_name.strip().capitalize()
if len(c_name) == 0:
    print("имя не может быть пустым!")
else:
    print("привет", c_name)
input("нажми Enter что бы закрыть")
