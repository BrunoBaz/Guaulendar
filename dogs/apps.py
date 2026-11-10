from django.apps import AppConfig


class DogsConfig(AppConfig):
    name = 'dogs'

    def ready(self):
        import dogs.signals
