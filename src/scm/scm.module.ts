import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ScmController } from './scm.controller';
import { ScmService } from './scm.service';
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
  providers: [ScmService, ScmRepositoryService],
  exports: [ScmService, ScmRepositoryService],
})
export class ScmModule {}
