from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from customer.models import DeliveryAssignment, Order


class Command(BaseCommand):
    help = (
        "Expire rider assignments that were not accepted in time "
        "and automatically assign the next available rider."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout-seconds",
            type=int,
            default=120,
            help="Seconds an Assigned delivery may wait before reassignment.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show expired assignments without changing anything.",
        )

    def handle(self, *args, **options):
        timeout_seconds = max(
            30,
            int(options["timeout_seconds"]),
        )

        dry_run = options["dry_run"]

        cutoff = (
            timezone.now()
            - timedelta(seconds=timeout_seconds)
        )

        assignment_ids = list(
            DeliveryAssignment.objects
            .filter(
                status="Assigned",
                assigned_at__lte=cutoff,
            )
            .values_list("id", flat=True)
        )

        if not assignment_ids:
            self.stdout.write(
                self.style.SUCCESS(
                    "No expired rider assignments found."
                )
            )
            return

        self.stdout.write(
            f"Expired assignments found: {len(assignment_ids)}"
        )

        for assignment_id in assignment_ids:

            if dry_run:
                assignment = (
                    DeliveryAssignment.objects
                    .select_related(
                        "order",
                        "delivery_partner",
                    )
                    .filter(pk=assignment_id)
                    .first()
                )

                if assignment:
                    self.stdout.write(
                        f"DRY RUN: #{assignment.order.order_number} "
                        f"-> {assignment.delivery_partner_id}"
                    )

                continue

            with transaction.atomic():

                assignment = (
                    DeliveryAssignment.objects
                    .select_for_update()
                    .select_related(
                        "order",
                        "delivery_partner",
                    )
                    .filter(pk=assignment_id)
                    .first()
                )

                if assignment is None:
                    continue

                # Rider may have accepted while this command was running.
                if assignment.status != "Assigned":
                    continue

                order = (
                    Order.objects
                    .select_for_update()
                    .get(pk=assignment.order_id)
                )

                # Never dispatch completed/cancelled orders.
                if order.status in {
                    "Cancelled",
                    "Delivered",
                }:
                    assignment.status = "Rejected"
                    assignment.save(
                        update_fields=["status"]
                    )

                    self.stdout.write(
                        f"Closed order skipped: "
                        f"#{order.order_number}"
                    )
                    continue

                # Timeout = rejected for dispatch purposes.
                # Existing rider exclusion logic prevents
                # the same rider receiving this order again.
                assignment.status = "Rejected"
                assignment.save(
                    update_fields=["status"]
                )

                # Lazy import avoids changing existing app startup flow.
                from customer.views import _assign_available_rider

                next_assignment = (
                    _assign_available_rider(order)
                )

                if next_assignment:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"#{order.order_number}: "
                            f"timed-out rider replaced by "
                            f"rider {next_assignment.delivery_partner_id}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"#{order.order_number}: "
                            f"no next rider available."
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "Automatic rider timeout check completed."
            )
        )
