import { Inject, Injectable, Logger } from '@nestjs/common';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import type { Cache } from 'cache-manager';
import { RdeQueryDto, TodosRegistrosDto, RegistrosIedDto } from './dto/rde.dto';
import { RdeTodosRegistros } from './entities/rde-todos-registros.entity';
import { RdeRegistrosIed } from './entities/rde-registros-ied.entity';

@Injectable()
export class RdeService {
  private readonly logger = new Logger(RdeService.name);
  private readonly cacheNamespace = 'rde';
  private readonly cacheTtlSeconds = 60 * 60 * 24;

  constructor(
    @Inject(CACHE_MANAGER) private readonly cache: Cache,
    @InjectRepository(RdeTodosRegistros)
    private readonly todosRepo: Repository<RdeTodosRegistros>,
    @InjectRepository(RdeRegistrosIed)
    private readonly iedRepo: Repository<RdeRegistrosIed>,
  ) {}

  async getTodosRegistros(
    query: RdeQueryDto,
  ): Promise<{ data: TodosRegistrosDto[]; total?: number }> {
    const cacheKey = this.buildCacheKey('todos-registros', query);
    return this.getCachedValue(cacheKey, async () => {
      const qb = this.todosRepo
        .createQueryBuilder('r')
        .orderBy('r.Ano', query.orderAno?.toUpperCase() === 'ASC' ? 'ASC' : 'DESC')
        .addOrderBy('r.Mes', query.orderMes?.toUpperCase() === 'ASC' ? 'ASC' : 'DESC');

      if (query.skip) qb.skip(query.skip);
      if (query.top) qb.take(query.top);

      const [rows, total] = await qb.getManyAndCount();

      const data: TodosRegistrosDto[] = rows.map((r) => ({
        CodigoRDE: r.CodigoRDE,
        NomePessoaNacional: r.NomePessoaNacional,
        UfPessoaNacional: r.UfPessoaNacional,
        NomePessoaEstrangeira: r.NomePessoaEstrangeira,
        PaisPessoaEstrangeira: r.PaisPessoaEstrangeira,
        MoedaOperacao: r.MoedaOperacao,
        ValorOperacao: r.ValorOperacao,
        Sistema: r.Sistema,
        Ocorrencia: r.Ocorrencia,
        Modalidade: r.Modalidade,
        Ano: r.Ano,
        Mes: r.Mes,
      }));

      this.logger.log(`getTodosRegistros: ${data.length} records returned`);
      return { data, total };
    });
  }

  async getRegistrosIed(
    query: RdeQueryDto,
  ): Promise<{ data: RegistrosIedDto[]; total?: number }> {
    const cacheKey = this.buildCacheKey('registros-ied', query);
    return this.getCachedValue(cacheKey, async () => {
      const qb = this.iedRepo
        .createQueryBuilder('r')
        .orderBy('r.Ano', query.orderAno?.toUpperCase() === 'ASC' ? 'ASC' : 'DESC')
        .addOrderBy('r.Mes', query.orderMes?.toUpperCase() === 'ASC' ? 'ASC' : 'DESC');

      if (query.skip) qb.skip(query.skip);
      if (query.top) qb.take(query.top);

      const [rows, total] = await qb.getManyAndCount();

      const data: RegistrosIedDto[] = rows.map((r) => ({
        CodigoRDE: r.CodigoRDE,
        CnpjBaseReceptora: r.CnpjBaseReceptora,
        NomePessoaNacional: r.NomePessoaNacional,
        UfPessoaNacional: r.UfPessoaNacional,
        NomePessoaEstrangeira: r.NomePessoaEstrangeira,
        PaisPessoaEstrangeira: r.PaisPessoaEstrangeira,
        MoedaOperacao: r.MoedaOperacao,
        ValorOperacao: r.ValorOperacao,
        Sistema: r.Sistema,
        Ocorrencia: r.Ocorrencia,
        Modalidade: r.Modalidade,
        Ano: r.Ano,
        Mes: r.Mes,
      }));

      this.logger.log(`getRegistrosIed: ${data.length} records returned`);
      return { data, total };
    });
  }

  private buildCacheKey(segment: string, payload: unknown): string {
    return `${this.cacheNamespace}:${segment}:${JSON.stringify(payload)}`;
  }

  private async getCachedValue<T>(key: string, resolver: () => Promise<T>): Promise<T> {
    if (!this.cache) return resolver();
    const cached = await this.cache.get<T>(key);
    if (cached !== undefined) return cached;
    const value = await resolver();
    await this.cache.set(key, value, this.cacheTtlSeconds);
    return value;
  }
}
