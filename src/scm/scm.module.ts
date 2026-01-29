import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ScmController } from './scm.controller';
import { ScmService } from './scm.service';
import { ScmCsvService } from './scm-csv.service';
import { ScmSchedulerService } from './scm-scheduler.service';
import { ScmRepositoryService } from './scm-repository.service';
import {
  Processo,
  FaseProcesso,
  TipoRequerimento,
  Municipio,
  Substancia,
  ProcessoMunicipio,
  ProcessoSubstancia,
} from './entities';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      Processo,
      FaseProcesso,
      TipoRequerimento,
      Municipio,
      Substancia,
      ProcessoMunicipio,
      ProcessoSubstancia,
    ]),
  ],
  controllers: [ScmController],
  providers: [ScmService, ScmCsvService, ScmSchedulerService, ScmRepositoryService],
  exports: [ScmService, ScmCsvService, ScmSchedulerService, ScmRepositoryService],
})
export class ScmModule {}
