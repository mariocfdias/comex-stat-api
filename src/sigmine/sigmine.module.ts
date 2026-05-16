import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { SigmineController } from './sigmine.controller';
import { SigmineService } from './sigmine.service';
import { SigmineLayerEntity } from './entities/sigmine-layer.entity';

@Module({
  imports: [TypeOrmModule.forFeature([SigmineLayerEntity])],
  controllers: [SigmineController],
  providers: [SigmineService],
})
export class SigmineModule {}
