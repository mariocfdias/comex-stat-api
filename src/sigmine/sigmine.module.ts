import { Module } from '@nestjs/common';
import { SigmineController } from './sigmine.controller';
import { SigmineService } from './sigmine.service';

@Module({
  controllers: [SigmineController],
  providers: [SigmineService],
})
export class SigmineModule {}
