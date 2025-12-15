
def show_env():
    with open('.env', 'r') as f:
        print(f.read())

if __name__ == "__main__":
    show_env()
