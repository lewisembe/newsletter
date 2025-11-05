"""
Archive Service Module
Creates paywall-free archive links using multiple services with fallback
"""
import requests
import time
import logging
from typing import Optional
from urllib.parse import quote

from config import settings

logger = logging.getLogger(__name__)


class ArchiveService:
    """Creates archive links to bypass paywalls"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def create_archive_link(self, url: str) -> str:
        """
        Create an archive link for the given URL using multiple services with fallback

        Args:
            url: Original URL to archive

        Returns:
            Archive URL or original URL if all services fail
        """
        if not url:
            return url

        # Try each service in order
        for service in settings.ARCHIVE_SERVICES:
            service = service.strip().lower()

            try:
                if service == 'archive.today':
                    archive_url = self._create_archive_today(url)
                elif service == 'web.archive.org':
                    archive_url = self._create_wayback_machine(url)
                elif service == '12ft.io':
                    archive_url = self._create_12ft(url)
                else:
                    logger.warning(f"Unknown archive service: {service}")
                    continue

                if archive_url:
                    logger.info(f"Created archive link using {service}: {archive_url[:80]}...")
                    return archive_url

            except Exception as e:
                logger.warning(f"Failed to create archive with {service}: {e}")
                continue

        # If all services fail, return original URL
        logger.warning(f"All archive services failed for {url}, returning original")
        return url

    def _create_archive_today(self, url: str) -> Optional[str]:
        """
        Create archive using archive.today/archive.is

        Args:
            url: URL to archive

        Returns:
            Archive URL or None
        """
        try:
            # First, check if URL is already archived
            search_url = f"https://archive.ph/{quote(url, safe='')}"

            # Try to submit for archiving
            submit_url = "https://archive.ph/submit/"
            data = {'url': url}

            response = self.session.post(submit_url, data=data, timeout=15, allow_redirects=True)

            if response.status_code == 200:
                # If successful, the redirected URL is the archive URL
                if 'archive.ph' in response.url or 'archive.is' in response.url:
                    return response.url

            # Fallback: construct URL (may or may not exist)
            return search_url

        except Exception as e:
            logger.debug(f"archive.today failed: {e}")
            return None

    def _create_wayback_machine(self, url: str) -> Optional[str]:
        """
        Create archive using Wayback Machine (archive.org)

        Args:
            url: URL to archive

        Returns:
            Archive URL or None
        """
        try:
            # Save URL to Wayback Machine
            save_url = f"https://web.archive.org/save/{url}"

            response = self.session.get(save_url, timeout=20, allow_redirects=True)

            if response.status_code == 200:
                # Extract archive URL from response
                if 'web.archive.org/web/' in response.url:
                    return response.url

            # Fallback: try to get latest snapshot
            snapshot_url = f"https://web.archive.org/web/{url}"
            return snapshot_url

        except Exception as e:
            logger.debug(f"Wayback Machine failed: {e}")
            return None

    def _create_12ft(self, url: str) -> Optional[str]:
        """
        Create paywall bypass using 12ft.io

        This service doesn't archive but removes paywalls

        Args:
            url: URL to process

        Returns:
            12ft.io URL
        """
        try:
            # 12ft.io simply prepends their domain
            bypass_url = f"https://12ft.io/{url}"

            # Quick check if the service is responding
            response = self.session.head(bypass_url, timeout=5)

            if response.status_code < 500:  # Accept any non-server-error response
                return bypass_url

        except Exception as e:
            logger.debug(f"12ft.io failed: {e}")

        return None

    def get_best_available_link(self, url: str, timeout_per_service: int = 5) -> str:
        """
        Try to get the best available archive link by testing each service

        Args:
            url: Original URL
            timeout_per_service: Seconds to wait for each service

        Returns:
            Best archive URL or original URL
        """
        for service in settings.ARCHIVE_SERVICES:
            try:
                if service == 'archive.today':
                    test_url = f"https://archive.ph/{quote(url, safe='')}"
                elif service == 'web.archive.org':
                    test_url = f"https://web.archive.org/web/{url}"
                elif service == '12ft.io':
                    test_url = f"https://12ft.io/{url}"
                else:
                    continue

                # Test if URL is accessible
                response = self.session.head(test_url, timeout=timeout_per_service, allow_redirects=True)

                if response.status_code == 200:
                    logger.info(f"Found working archive: {test_url[:80]}...")
                    return test_url

            except Exception as e:
                logger.debug(f"Service {service} not available: {e}")
                continue

        return url


# Convenience functions
def create_archive(url: str) -> str:
    """Create archive link for a URL"""
    service = ArchiveService()
    return service.create_archive_link(url)


def get_best_link(url: str) -> str:
    """Get best available archive link for a URL"""
    service = ArchiveService()
    return service.get_best_available_link(url)


if __name__ == '__main__':
    # Test archive services
    service = ArchiveService()

    test_urls = [
        'https://www.ft.com/content/example',
        'https://www.wsj.com/articles/example',
    ]

    print("Testing archive services...")

    for url in test_urls:
        print(f"\nOriginal: {url}")
        archive_url = service.create_archive_link(url)
        print(f"Archive:  {archive_url}")
