import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
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
export class ScmRepositoryService {
  private readonly logger = new Logger(ScmRepositoryService.name);

  constructor(
    @InjectRepository(Processo)
    private readonly processoRepository: Repository<Processo>,
    @InjectRepository(FaseProcesso)
    private readonly faseProcessoRepository: Repository<FaseProcesso>,
    @InjectRepository(TipoRequerimento)
    private readonly tipoRequerimentoRepository: Repository<TipoRequerimento>,
    @InjectRepository(Municipio)
    private readonly municipioRepository: Repository<Municipio>,
    @InjectRepository(Substancia)
    private readonly substanciaRepository: Repository<Substancia>,
    @InjectRepository(ProcessoMunicipio)
    private readonly processoMunicipioRepository: Repository<ProcessoMunicipio>,
    @InjectRepository(ProcessoSubstancia)
    private readonly processoSubstanciaRepository: Repository<ProcessoSubstancia>,
  ) {}

  // Bulk insert methods for CSV data import with chunking
  async bulkInsertProcessos(processos: Partial<Processo>[]): Promise<void> {
    this.logger.log(`Clearing processos table and inserting ${processos.length} records...`);
    await this.processoRepository.clear();
    
    // Remove duplicates based on primary key (DSProcesso)
    const uniqueProcessos = this.removeDuplicatesProcessos(processos);
    this.logger.log(`Removed ${processos.length - uniqueProcessos.length} duplicate processos`);
    
    const chunkSize = 500; // Smaller chunks for large table
    for (let i = 0; i < uniqueProcessos.length; i += chunkSize) {
      const chunk = uniqueProcessos.slice(i, i + chunkSize);
      try {
        await this.processoRepository.save(chunk);
        this.logger.debug(`Inserted chunk ${Math.floor(i/chunkSize) + 1}/${Math.ceil(uniqueProcessos.length/chunkSize)}`);
      } catch (error) {
        this.logger.error(`Error inserting processos chunk ${i}-${i+chunkSize}:`, error);
        throw error;
      }
    }
  }

  async bulkInsertFaseProcesso(fases: Partial<FaseProcesso>[]): Promise<void> {
    this.logger.log(`Clearing fase_processo table and inserting ${fases.length} records...`);
    await this.faseProcessoRepository.clear();
    await this.faseProcessoRepository.save(fases);
  }

  async bulkInsertTipoRequerimento(tipos: Partial<TipoRequerimento>[]): Promise<void> {
    this.logger.log(`Clearing tipo_requerimento table and inserting ${tipos.length} records...`);
    await this.tipoRequerimentoRepository.clear();
    await this.tipoRequerimentoRepository.save(tipos);
  }

  async bulkInsertMunicipios(municipios: Partial<Municipio>[]): Promise<void> {
    this.logger.log(`Clearing municipios table and inserting ${municipios.length} records...`);
    await this.municipioRepository.clear();
    await this.municipioRepository.save(municipios);
  }

  async bulkInsertSubstancias(substancias: Partial<Substancia>[]): Promise<void> {
    this.logger.log(`Clearing substancias table and inserting ${substancias.length} records...`);
    await this.substanciaRepository.clear();
    await this.substanciaRepository.save(substancias);
  }

  async bulkInsertProcessoMunicipios(relacoes: Partial<ProcessoMunicipio>[]): Promise<void> {
    this.logger.log(`Clearing processo_municipio table and inserting ${relacoes.length} relations...`);
    await this.processoMunicipioRepository.clear();
    
    // Remove duplicates based on primary key (DSProcesso + IDMunicipio)
    const uniqueRelacoes = this.removeDuplicatesProcessoMunicipio(relacoes);
    this.logger.log(`Removed ${relacoes.length - uniqueRelacoes.length} duplicate processo-municipio relations`);
    
    // Insert in smaller chunks to avoid memory issues
    const chunkSize = 500;
    for (let i = 0; i < uniqueRelacoes.length; i += chunkSize) {
      const chunk = uniqueRelacoes.slice(i, i + chunkSize);
      try {
        await this.processoMunicipioRepository.save(chunk as any);
        this.logger.debug(`Inserted PM chunk ${Math.floor(i/chunkSize) + 1}/${Math.ceil(uniqueRelacoes.length/chunkSize)}`);
      } catch (error) {
        this.logger.error(`Error inserting processo-municipio chunk ${i}-${i+chunkSize}:`, error);
        // Try inserting one by one to skip problematic records
        for (const item of chunk) {
          try {
            await this.processoMunicipioRepository.save(item);
          } catch (itemError) {
            this.logger.warn(`Skipping duplicate processo-municipio: ${item.DSProcesso}-${item.IDMunicipio}`);
          }
        }
      }
    }
  }

  async bulkInsertProcessoSubstancias(relacoes: Partial<ProcessoSubstancia>[]): Promise<void> {
    this.logger.log(`Clearing processo_substancia table and inserting ${relacoes.length} relations...`);
    await this.processoSubstanciaRepository.clear();
    
    // Remove duplicates based on primary key (DSProcesso + IDSubstancia)
    const uniqueRelacoes = this.removeDuplicatesProcessoSubstancia(relacoes);
    this.logger.log(`Removed ${relacoes.length - uniqueRelacoes.length} duplicate processo-substancia relations`);
    
    // Insert in smaller chunks to avoid memory issues
    const chunkSize = 500;
    for (let i = 0; i < uniqueRelacoes.length; i += chunkSize) {
      const chunk = uniqueRelacoes.slice(i, i + chunkSize);
      try {
        // Use INSERT OR IGNORE to handle any remaining duplicates
        await this.processoSubstanciaRepository.save(chunk as any);
        this.logger.debug(`Inserted PS chunk ${Math.floor(i/chunkSize) + 1}/${Math.ceil(uniqueRelacoes.length/chunkSize)}`);
      } catch (error) {
        this.logger.error(`Error inserting processo-substancia chunk ${i}-${i+chunkSize}:`, error);
        // Try inserting one by one to skip problematic records
        for (const item of chunk) {
          try {
            await this.processoSubstanciaRepository.save(item);
          } catch (itemError) {
            this.logger.warn(`Skipping duplicate processo-substancia: ${item.DSProcesso}-${item.IDSubstancia}`);
          }
        }
      }
    }
  }

  private removeDuplicatesProcessoMunicipio(relacoes: Partial<ProcessoMunicipio>[]): Partial<ProcessoMunicipio>[] {
    const seen = new Set<string>();
    return relacoes.filter(rel => {
      const key = `${rel.DSProcesso}|${rel.IDMunicipio}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  private removeDuplicatesProcessoSubstancia(relacoes: Partial<ProcessoSubstancia>[]): Partial<ProcessoSubstancia>[] {
    const seen = new Set<string>();
    return relacoes.filter(rel => {
      const key = `${rel.DSProcesso}|${rel.IDSubstancia}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  private removeDuplicatesProcessos(processos: Partial<Processo>[]): Partial<Processo>[] {
    const seen = new Set<string>();
    return processos.filter(proc => {
      const key = proc.DSProcesso;
      if (!key || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  // Query methods
  async findAllProcessos(): Promise<Processo[]> {
    return this.processoRepository.find();
  }

  async findAllFases(): Promise<FaseProcesso[]> {
    return this.faseProcessoRepository.find();
  }

  async findAllTipos(): Promise<TipoRequerimento[]> {
    return this.tipoRequerimentoRepository.find();
  }

  async findAllMunicipios(): Promise<Municipio[]> {
    return this.municipioRepository.find();
  }

  async findAllSubstancias(): Promise<Substancia[]> {
    return this.substanciaRepository.find();
  }

  async findAllProcessoMunicipios(): Promise<ProcessoMunicipio[]> {
    return this.processoMunicipioRepository.find();
  }

  async findAllProcessoSubstancias(): Promise<ProcessoSubstancia[]> {
    return this.processoSubstanciaRepository.find();
  }

  // Analytics queries
  async getProcessosByFase(): Promise<{ fase: string; count: number }[]> {
    const result = await this.processoRepository
      .createQueryBuilder('p')
      .leftJoin(FaseProcesso, 'f', 'p.IDFaseProcesso = f.IDFaseProcesso')
      .select('f.DSFaseProcesso', 'fase')
      .addSelect('COUNT(*)', 'count')
      .groupBy('f.DSFaseProcesso')
      .getRawMany();
    
    return result.map(r => ({
      fase: r.fase || 'Unknown',
      count: parseInt(r.count) || 0
    }));
  }

  async getProcessosByTipo(): Promise<{ tipo: string; count: number }[]> {
    const result = await this.processoRepository
      .createQueryBuilder('p')
      .leftJoin(TipoRequerimento, 't', 'p.IDTipoRequerimento = t.IDTipoRequerimento')
      .select('t.DSTipoRequerimento', 'tipo')
      .addSelect('COUNT(*)', 'count')
      .groupBy('t.DSTipoRequerimento')
      .getRawMany();
    
    return result.map(r => ({
      tipo: r.tipo || 'Unknown',
      count: parseInt(r.count) || 0
    }));
  }

  async getProcessosByMunicipio(): Promise<{ municipio: string; count: number }[]> {
    const result = await this.processoMunicipioRepository
      .createQueryBuilder('pm')
      .leftJoin(Municipio, 'm', 'pm.IDMunicipio = m.IDMunicipio')
      .select('m.NMMunicipio', 'municipio')
      .addSelect('COUNT(*)', 'count')
      .groupBy('m.NMMunicipio')
      .getRawMany();
    
    return result.map(r => ({
      municipio: r.municipio || 'Unknown',
      count: parseInt(r.count) || 0
    }));
  }

  async getProcessosBySubstancia(): Promise<{ substancia: string; count: number }[]> {
    const result = await this.processoSubstanciaRepository
      .createQueryBuilder('ps')
      .leftJoin(Substancia, 's', 'ps.IDSubstancia = s.IDSubstancia')
      .select('s.NMSubstancia', 'substancia')
      .addSelect('COUNT(*)', 'count')
      .groupBy('s.NMSubstancia')
      .getRawMany();
    
    return result.map(r => ({
      substancia: r.substancia || 'Unknown',
      count: parseInt(r.count) || 0
    }));
  }

  async getProcessosByUF(): Promise<{ uf: string; count: number }[]> {
    const result = await this.processoMunicipioRepository
      .createQueryBuilder('pm')
      .leftJoin(Municipio, 'm', 'pm.IDMunicipio = m.IDMunicipio')
      .select('m.SGUF', 'uf')
      .addSelect('COUNT(*)', 'count')
      .groupBy('m.SGUF')
      .getRawMany();
    
    return result.map(r => ({
      uf: r.uf || 'Unknown',
      count: parseInt(r.count) || 0
    }));
  }

  // Data summary
  async getDataCounts(): Promise<{
    processos: number;
    fases: number;
    tipos: number;
    municipios: number;
    substancias: number;
    processoMunicipios: number;
    processoSubstancias: number;
  }> {
    const [
      processos,
      fases,
      tipos,
      municipios,
      substancias,
      processoMunicipios,
      processoSubstancias,
    ] = await Promise.all([
      this.processoRepository.count(),
      this.faseProcessoRepository.count(),
      this.tipoRequerimentoRepository.count(),
      this.municipioRepository.count(),
      this.substanciaRepository.count(),
      this.processoMunicipioRepository.count(),
      this.processoSubstanciaRepository.count(),
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

  // Check if data exists
  async hasData(): Promise<boolean> {
    const count = await this.processoRepository.count();
    return count > 0;
  }

  // Find processos by filters
  async findProcessosByFilters(filters: {
    processo?: string;
    municipio?: number;
    substancia?: number;
    fase?: number;
    tipo?: number;
    limit?: number;
  }): Promise<Processo[]> {
    const query = this.processoRepository.createQueryBuilder('p');

    if (filters.processo) {
      query.andWhere('p.DSProcesso = :processo', { processo: filters.processo });
    }
    
    if (filters.fase) {
      query.andWhere('p.IDFaseProcesso = :fase', { fase: filters.fase });
    }
    
    if (filters.tipo) {
      query.andWhere('p.IDTipoRequerimento = :tipo', { tipo: filters.tipo });
    }

    if (filters.municipio) {
      query.innerJoin('processo_municipio', 'pm', 'pm.DSProcesso = p.DSProcesso');
      query.andWhere('pm.IDMunicipio = :municipio', { municipio: filters.municipio });
    }

    if (filters.substancia) {
      query.innerJoin('processo_substancia', 'ps', 'ps.DSProcesso = p.DSProcesso');
      query.andWhere('ps.IDSubstancia = :substancia', { substancia: filters.substancia });
    }

    if (filters.limit) {
      query.limit(filters.limit);
    }

    return query.getMany();
  }
}