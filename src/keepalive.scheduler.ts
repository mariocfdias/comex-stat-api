import { Cron, CronExpression } from '@nestjs/schedule';
import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';

@Injectable()
export class KeepaliveScheduler {
  private readonly logger = new Logger(KeepaliveScheduler.name);

  @Cron(CronExpression.EVERY_10_MINUTES)
  async handlePing(): Promise<void> {
    const pingUrl = process.env.SELF_PING_URL;

    if (!pingUrl) {
      this.logger.warn('SELF_PING_URL is not set. Skipping keepalive ping.');
      return;
    }

    try {
      await axios.get(pingUrl, { timeout: 5_000 });
      this.logger.debug(`Keepalive ping succeeded: ${pingUrl}`);
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'Unknown error';
      this.logger.warn(`Keepalive ping failed for ${pingUrl}: ${reason}`);
    }
  }
}
