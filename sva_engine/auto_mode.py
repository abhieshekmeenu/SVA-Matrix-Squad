class AutoMode:
    def __init__(self, controller):
        self.controller = controller
        self.running = False
        self.paused = False
        self.current_step = 0
        self.results = []
        self.commands = []

    def start(self, commands):
        self.commands = list(commands)
        self.running = True
        self.paused = False
        self.current_step = 0
        self.results = []

        return self._run_from_current()

    def _run_from_current(self):
        for index in range(self.current_step, len(self.commands)):
            if not self.running or self.paused:
                break

            self.current_step = index + 1
            result = self.controller.execute(self.commands[index])
            self.results.append(result)

            if not result.get("success", False):
                self.running = False
                break

        if not self.paused:
            self.running = False

        return self.results

    def pause(self):
        self.paused = True

    def stop(self):
        self.running = False
        self.paused = False

    def resume(self, commands=None):
        if commands is not None:
            self.commands = list(commands)

        if self.current_step >= len(self.commands):
            return self.results

        self.running = True
        self.paused = False
        return self._run_from_current()
