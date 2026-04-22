import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from auto_tickets.itsr_file_utils import delete_attachments_for_ticket_number, get_itsr_files_dir
from auto_tickets.models import ITSR_Network

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=ITSR_Network)
def delete_itsr_files_when_ticket_deleted(sender, instance, **kwargs):
    n = delete_attachments_for_ticket_number(get_itsr_files_dir(), instance.itsr_ticket_number)
    if n:
        logger.info(
            'Removed %s ITSR attachment(s) for deleted ticket %s',
            n,
            instance.itsr_ticket_number,
        )
