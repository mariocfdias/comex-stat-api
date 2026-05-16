import { Injectable, Logger } from '@nestjs/common';
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

@Injectable()
export class ScmService {
  private readonly logger = new Logger(ScmService.name);

  constructor(private readonly repositoryService: ScmRepositoryService) {}

  async getProcessos(): Promise<Processo[]> {
    return this.repositoryService.findAllProcessos();
  }

  async getFases(): Promise<FaseProcesso[]> {
    return this.repositoryService.findAllFases();
  }

  async getTipos(): Promise<TipoRequerimento[]> {
    return this.repositoryService.findAllTipos();
  }

  async getMunicipios(): Promise<Municipio[]> {
    return this.repositoryService.findAllMunicipios();
  }

  async getSubstancias(): Promise<Substancia[]> {
    return this.repositoryService.findAllSubstancias();
  }

  async getProcessoMunicipios(): Promise<ProcessoMunicipio[]> {
    return this.repositoryService.findAllProcessoMunicipios();
  }

  async getProcessoSubstancias(): Promise<ProcessoSubstancia[]> {
    return this.repositoryService.findAllProcessoSubstancias();
  }

  async getAllData() {
    const [processos, fases, tipos, municipios, substancias, processoMunicipios, processoSubstancias] =
      await Promise.all([
        this.getProcessos(), this.getFases(), this.getTipos(),
        this.getMunicipios(), this.getSubstancias(),
        this.getProcessoMunicipios(), this.getProcessoSubstancias(),
      ]);
    return { processos, fases, tipos, municipios, substancias, processoMunicipios, processoSubstancias };
  }

  async getProcessosByFase(): Promise<{ [fase: string]: number }> {
    const result = await this.repositoryService.getProcessosByFase();
    return Object.fromEntries(result.map((r) => [r.fase, r.count]));
  }

  async getProcessosByTipo(): Promise<{ [tipo: string]: number }> {
    const result = await this.repositoryService.getProcessosByTipo();
    return Object.fromEntries(result.map((r) => [r.tipo, r.count]));
  }

  async getProcessosByMunicipio(): Promise<{ [municipio: string]: number }> {
    const result = await this.repositoryService.getProcessosByMunicipio();
    return Object.fromEntries(result.map((r) => [r.municipio, r.count]));
  }

  async getProcessosBySubstancia(): Promise<{ [substancia: string]: number }> {
    const result = await this.repositoryService.getProcessosBySubstancia();
    return Object.fromEntries(result.map((r) => [r.substancia, r.count]));
  }

  async getProcessosByUF(): Promise<{ [uf: string]: number }> {
    const result = await this.repositoryService.getProcessosByUF();
    return Object.fromEntries(result.map((r) => [r.uf, r.count]));
  }

  async getDataSummary() {
    const counts = await this.repositoryService.getDataCounts();
    return {
      lastUpdate: new Date().toISOString(),
      counts,
      analytics: {
        processosByFase: await this.getProcessosByFase(),
        processosByTipo: await this.getProcessosByTipo(),
        processosByUF: await this.getProcessosByUF(),
      },
    };
  }

  async findProcessosByFilters(filters: {
    processo?: string;
    municipio?: number;
    substancia?: number;
    fase?: number;
    tipo?: number;
    limit?: number;
  }): Promise<Processo[]> {
    return this.repositoryService.findProcessosByFilters(filters);
  }

  async getDataCounts() {
    return this.repositoryService.getDataCounts();
  }

  async triggerManualUpdate(): Promise<void> {
    this.logger.warn(
      'Manual update triggered via API. Data ingestion is now managed by Airflow — trigger the scm_ingest DAG instead.',
    );
  }
}
