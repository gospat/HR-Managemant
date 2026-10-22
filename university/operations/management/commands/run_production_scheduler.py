from base.management.commands.run_scheduler import Command as SchedulerCommand
from horilla.scheduling import register_job
from university.operations.health import scheduler_heartbeat


class Command(SchedulerCommand):
    help = "Run one scheduler with a shared, expiring health heartbeat."

    def _load_job_modules(self):
        super()._load_job_modules()
        register_job(
            scheduler_heartbeat,
            "interval",
            job_id="university_scheduler_heartbeat",
            seconds=15,
        )
        scheduler_heartbeat()
