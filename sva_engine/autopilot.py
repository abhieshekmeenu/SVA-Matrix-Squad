from .error_analyzer import ErrorAnalyzer


class AutopilotLoop:
    """JARVIS Observe -> Think -> Act -> Verify loop."""

    def __init__(self, controller, max_retries=2, error_analyzer=None):
        self.controller = controller
        self.max_retries = max(0, int(max_retries))
        self.error_analyzer = error_analyzer or ErrorAnalyzer()
        self.running = False
        self.paused = False
        self.current_step = 0
        self.history = []
        self._commands = []

    def observe(self, result):
        return {
            "success": result.get("success", False),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "returncode": result.get("returncode"),
        }

    def think(self, observation, command):
        if observation["success"]:
            return {"action": "verify", "command": command}

        error = observation.get("stderr") or "Unknown error"
        return {
            "action": "retry",
            "command": command,
            "error": error,
            "analysis": f"Command failed: {error}",
        }

    def act(self, command):
        return self.controller.execute(command)

    def verify(self, result):
        return result.get("success", False)

    def _execute_step(self, command):
        if not isinstance(command, str) or not command.strip():
            self.history.append({
                "step": self.current_step,
                "command": command,
                "attempt": 0,
                "observation": {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "returncode": None,
                },
                "decision": {
                    "action": "stop",
                    "reason": "Empty command",
                },
                "error_analysis": None,
                "verified": False,
                "result": {
                    "success": False,
                    "reason": "Empty command",
                },
            })
            return False

        command = command.strip()
        attempts = 0

        while attempts <= self.max_retries:
            if not self.running or self.paused:
                break

            attempts += 1
            result = self.act(command)
            observation = self.observe(result)
            decision = self.think(observation, command)
            recovery = None

            if not observation["success"]:
                recovery = self.error_analyzer.analyze(command, result)
                decision["recovery"] = recovery

            verified = self.verify(result)

            self.history.append({
                "step": self.current_step,
                "command": command,
                "attempt": attempts,
                "observation": observation,
                "decision": decision,
                "error_analysis": recovery,
                "verified": verified,
                "result": result,
            })

            if verified:
                return True

        return False

    def run(self, commands):
        self.running = True
        self.paused = False
        self.current_step = 0
        self.history = []
        self._commands = list(commands)

        while self.current_step < len(self._commands):
            if not self.running or self.paused:
                break

            command = self._commands[self.current_step]
            self.current_step += 1

            if not self._execute_step(command):
                self.running = False
                break

        if not self.paused:
            self.running = False

        return self.history

    def pause(self):
        self.paused = True

    def resume(self):
        if self.current_step >= len(self._commands):
            return self.history

        self.running = True
        self.paused = False

        while self.current_step < len(self._commands):
            if not self.running or self.paused:
                break

            command = self._commands[self.current_step]
            self.current_step += 1

            if not self._execute_step(command):
                self.running = False
                break

        if not self.paused:
            self.running = False

        return self.history

    def stop(self):
        self.running = False
        self.paused = False
