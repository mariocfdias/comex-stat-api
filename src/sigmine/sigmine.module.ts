import { Module } from '@nestjs/common';
import { SigmineController } from './sigmine.controller';
import { SigmineService } from './sigmine.service';
import { GeographicFilterService } from './services/geographic-filter.service';

@Module({
  controllers: [SigmineController],
  providers: [SigmineService, GeographicFilterService],
})
export class SigmineModule {}
