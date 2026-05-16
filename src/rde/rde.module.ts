import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { RdeController } from './rde.controller';
import { RdeService } from './rde.service';
import { RdeTodosRegistros } from './entities/rde-todos-registros.entity';
import { RdeRegistrosIed } from './entities/rde-registros-ied.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([RdeTodosRegistros, RdeRegistrosIed]),
  ],
  controllers: [RdeController],
  providers: [RdeService],
  exports: [RdeService],
})
export class RdeModule {}
