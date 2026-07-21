def hello_world(**kwargs):
    try:
        nome = kwargs.get('name', 'Mondo')
        return f'Ciao, {nome}!'
    except Exception as e:
        return f'Errore: {str(e)}'

if __name__ == "__main__":
    print(hello_world())
    print(hello_world(name='Mario'))