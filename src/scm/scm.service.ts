import { Injectable, Logger, OnApplicationBootstrap } from '@nestjs/common';
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

@Injectable()
export class ScmService implements OnApplicationBootstrap {
  private readonly logger = new Logger(ScmService.name);

  constructor(
    private readonly csvService: ScmCsvService,
    private readonly schedulerService: ScmSchedulerService,
    private readonly repositoryService: ScmRepositoryService,
  ) {}

  async onApplicationBootstrap(): Promise<void> {
    // Load initial data if database is empty
    // TEMPORARILY DISABLED: uncomment after fixing data download
    // await this.schedulerService.loadInitialDataIfNeeded();
    this.logger.log('Skipping initial data load. Use manual trigger to load data.');
  }

  // Data retrieval methods (now from database)
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
    const [
      processos,
      fases,
      tipos,
      municipios,
      substancias,
      processoMunicipios,
      processoSubstancias,
    ] = await Promise.all([
      this.getProcessos(),
      this.getFases(),
      this.getTipos(),
      this.getMunicipios(),
      this.getSubstancias(),
      this.getProcessoMunicipios(),
      this.getProcessoSubstancias(),
    ]);

    return {
      processos,
      fases,
      tipos,
      municipios,
      substancias,
      processoMunicipios,
      processoSubstancias,
    };
  }

  // Analytics methods (using database queries)
  async getProcessosByFase(): Promise<{ [fase: string]: number }> {
    const result = await this.repositoryService.getProcessosByFase();
    const faseCount: { [fase: string]: number } = {};
    
    result.forEach(item => {
      faseCount[item.fase] = item.count;
    });
    
    return faseCount;
  }

  async getProcessosByTipo(): Promise<{ [tipo: string]: number }> {
    const result = await this.repositoryService.getProcessosByTipo();
    const tipoCount: { [tipo: string]: number } = {};
    
    result.forEach(item => {
      tipoCount[item.tipo] = item.count;
    });
    
    return tipoCount;
  }

  async getProcessosByMunicipio(): Promise<{ [municipio: string]: number }> {
    const result = await this.repositoryService.getProcessosByMunicipio();
    const municipioCount: { [municipio: string]: number } = {};
    
    result.forEach(item => {
      municipioCount[item.municipio] = item.count;
    });
    
    return municipioCount;
  }

  async getProcessosBySubstancia(): Promise<{ [substancia: string]: number }> {
    const result = await this.repositoryService.getProcessosBySubstancia();
    const substanciaCount: { [substancia: string]: number } = {};
    
    result.forEach(item => {
      substanciaCount[item.substancia] = item.count;
    });
    
    return substanciaCount;
  }

  async getProcessosByUF(): Promise<{ [uf: string]: number }> {
    const result = await this.repositoryService.getProcessosByUF();
    const ufCount: { [uf: string]: number } = {};
    
    result.forEach(item => {
      ufCount[item.uf] = item.count;
    });
    
    return ufCount;
  }

  // Manual update methods
  async triggerManualUpdate(): Promise<void> {
    return this.schedulerService.triggerManualUpdate();
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

  // Search/filter methods
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
}
