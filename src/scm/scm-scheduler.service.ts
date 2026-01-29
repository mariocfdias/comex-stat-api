import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { ScmCsvService } from './scm-csv.service';

@Injectable()
export class ScmSchedulerService {
  private readonly logger = new Logger(ScmSchedulerService.name);

  constructor(private readonly csvService: ScmCsvService) {}

  @Cron(CronExpression.EVERY_DAY_AT_2AM, {
    name: 'scm-daily-update',
    timeZone: 'America/Sao_Paulo',
  })
  async handleDailyDataUpdate(): Promise<void> {
    this.logger.log('Starting daily SCM data update...');

    try {
      // Download and extract the latest data
      await this.csvService.downloadAndExtractData();

      // Load data to database
      await this.csvService.loadDataToDatabase();

      this.logger.log('Daily SCM data update completed successfully');
    } catch (error) {
      this.logger.error('Failed to update SCM data:', error);
      throw error;
    }
  }

  // Manual trigger for data update
  async triggerManualUpdate(): Promise<void> {
    this.logger.log('Manual SCM data update triggered...');
    await this.handleDailyDataUpdate();
  }

  // Load static data on startup if database is empty
  async loadInitialDataIfNeeded(): Promise<void> {
    const hasData = await this.csvService.isDataLoadedInDatabase();
    
    if (!hasData) {
      this.logger.log('No data found in database, loading initial data from static files...');
      await this.csvService.loadDataToDatabase();
      this.logger.log('Initial data loaded successfully');
    } else {
      this.logger.log('Data already exists in database');
    }
  }
}
