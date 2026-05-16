import { Injectable, Logger } from '@nestjs/common';
import { ScmRepositoryService } from './scm-repository.service';
import axios from 'axios';
import { createWriteStream, createReadStream } from 'fs';
import { pipeline } from 'stream/promises';
import * as path from 'path';
import * as fs from 'fs/promises';
import AdmZip = require('adm-zip');
import * as readline from 'readline';
import * as https from 'https';
import {
  ProcessoEntity,
  FaseProcessoEntity,
  TipoRequerimentoEntity,
  MunicipioEntity,
  SubstanciaEntity,
  ProcessoMunicipioEntity,
  ProcessoSubstanciaEntity,
} from './entities';

@Injectable()
export class ScmCsvService {
  private readonly logger = new Logger(ScmCsvService.name);
  private readonly downloadUrl =
    'https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip';
  private readonly dataDirectory = path.join(process.cwd(), 'data', 'scm');

  constructor(private readonly repositoryService: ScmRepositoryService) {
    void this.ensureDataDirectory();
  }

  private async ensureDataDirectory(): Promise<void> {
    try {
      await fs.mkdir(this.dataDirectory, { recursive: true });
    } catch (error) {
      this.logger.error('Failed to create data directory:', error);
    }
  }

  private async isDataFresh(): Promise<boolean> {
    try {
      // Check if extracted files exist and are less than 48 hours old
      const extractedDir = path.join(this.dataDirectory, 'extracted', 'microdados-scm');
      const processoFile = path.join(extractedDir, 'Processo.txt');

      // Check if the main file exists
      const existsSync = require('fs').existsSync as (path: string) => boolean;
      if (!existsSync(processoFile)) {
        return false;
      }

      // Check file modification time
      const stats = await fs.stat(processoFile);
      const fileAge = Date.now() - stats.mtime.getTime();
      const maxAge = 48 * 60 * 60 * 1000; // 48 hours in milliseconds

      const isFresh = fileAge < maxAge;

      if (isFresh) {
        const ageInHours = Math.floor(fileAge / (60 * 60 * 1000));
        this.logger.log(`Data files are ${ageInHours} hours old (fresh, skipping download)`);
      }

      return isFresh;
    } catch (error) {
      return false;
    }
  }

  async downloadAndExtractData(): Promise<void> {
    // Check if we have fresh data (less than 48 hours old)
    const dataIsFresh = await this.isDataFresh();

    if (dataIsFresh) {
      this.logger.log('Using existing data files (less than 48 hours old)');
      return;
    }

    this.logger.log('Starting download of SCM data...');

    const zipPath = path.join(this.dataDirectory, 'microdados-scm.zip');
    const maxRetries = 3;
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        this.logger.log(`Download attempt ${attempt}/${maxRetries}...`);

        // Create HTTPS agent with better configuration
        const httpsAgent = new https.Agent({
          rejectUnauthorized: false,
          keepAlive: true,
          keepAliveMsecs: 60000,
          timeout: 120000, // 2 minutes for connection
        });

        // Download zip file with separate timeouts
        this.logger.log('Downloading zip file from ANM...');
        const response = await axios({
          method: 'GET',
          url: this.downloadUrl,
          responseType: 'stream',
          timeout: 600000, // 10 minutes total timeout
          httpsAgent,
          // Add headers to appear more like a browser
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/zip, */*',
            'Accept-Encoding': 'gzip, deflate, br',
          },
          maxRedirects: 5,
        });

        // Save to file
        const writer = createWriteStream(zipPath);
        await pipeline(response.data, writer);

        this.logger.log('Download completed, extracting files...');

        // Extract zip file
        await this.extractZipFile(zipPath);

        this.logger.log('Data extraction completed successfully');
        return; // Success, exit the retry loop
      } catch (error) {
        lastError = error as Error;
        this.logger.error(`Attempt ${attempt} failed:`, error.message);

        if (attempt < maxRetries) {
          const waitTime = Math.min(1000 * Math.pow(2, attempt - 1), 30000); // Exponential backoff, max 30s
          this.logger.log(`Retrying in ${waitTime / 1000} seconds...`);
          await new Promise((resolve) => setTimeout(resolve, waitTime));
        }
      }
    }

    // If we get here, all retries failed
    this.logger.error('All download attempts failed');
    throw lastError || new Error('Download failed after all retries');
  }

  private async extractZipFile(zipPath: string): Promise<void> {
    try {
      const zip = new AdmZip(zipPath);
      const outputPath = path.join(this.dataDirectory, 'extracted');

      await fs.mkdir(outputPath, { recursive: true });

      // Extract all files from the zip
      zip.extractAllTo(outputPath, true);

      this.logger.log(`Extracted zip file to ${outputPath}`);
    } catch (error) {
      this.logger.error('Failed to extract zip file:', error);
      throw error;
    }
  }

  async parseProcessoFile(): Promise<ProcessoEntity[]> {
    return this.parseCSVFile<ProcessoEntity>(
      'Processo.txt',
      this.parseProcessoLine.bind(this),
    );
  }

  async parseFaseProcessoFile(): Promise<FaseProcessoEntity[]> {
    return this.parseCSVFile<FaseProcessoEntity>(
      'FaseProcesso.txt',
      this.parseFaseProcessoLine.bind(this),
    );
  }

  async parseTipoRequerimentoFile(): Promise<TipoRequerimentoEntity[]> {
    return this.parseCSVFile<TipoRequerimentoEntity>(
      'TipoRequerimento.txt',
      this.parseTipoRequerimentoLine.bind(this),
    );
  }

  async parseMunicipioFile(): Promise<MunicipioEntity[]> {
    return this.parseCSVFile<MunicipioEntity>(
      'Municipio.txt',
      this.parseMunicipioLine.bind(this),
    );
  }

  async parseSubstanciaFile(): Promise<SubstanciaEntity[]> {
    return this.parseCSVFile<SubstanciaEntity>(
      'Substancia.txt',
      this.parseSubstanciaLine.bind(this),
    );
  }

  async parseProcessoMunicipioFile(): Promise<ProcessoMunicipioEntity[]> {
    return this.parseCSVFile<ProcessoMunicipioEntity>(
      'ProcessoMunicipio.txt',
      this.parseProcessoMunicipioLine.bind(this),
    );
  }

  async parseProcessoSubstanciaFile(): Promise<ProcessoSubstanciaEntity[]> {
    return this.parseCSVFile<ProcessoSubstanciaEntity>(
      'ProcessoSubstancia.txt',
      this.parseProcessoSubstanciaLine.bind(this),
    );
  }

  private async parseCSVFile<T>(
    fileName: string,
    lineParser: (line: string) => T | null,
  ): Promise<T[]> {
    const filePath = this.getFilePath(fileName);
    const results: T[] = [];

    try {
      const fileStream = createReadStream(filePath);
      const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity,
      });

      let lineNumber = 0;
      for await (const line of rl) {
        lineNumber++;

        // Skip header line
        if (lineNumber === 1) continue;

        // Skip empty lines
        if (!line.trim()) continue;

        const parsed = lineParser(line);
        if (parsed) {
          results.push(parsed);
        }

        // Log progress for large files
        if (lineNumber % 10000 === 0) {
          this.logger.debug(`Processed ${lineNumber} lines from ${fileName}`);
        }
      }

      this.logger.log(`Parsed ${results.length} records from ${fileName}`);
      return results;
    } catch (error) {
      this.logger.error(`Failed to parse file ${fileName}:`, error);
      throw error;
    }
  }

  private getFilePath(fileName: string): string {
    // Try multiple possible locations for the file
    const staticPath = path.join(process.cwd(), 'static', 'SCM', fileName);
    const extractedPath = path.join(this.dataDirectory, 'extracted', fileName);
    const extractedSubPath = path.join(this.dataDirectory, 'extracted', 'microdados-scm', fileName);
    const dataPath = path.join(this.dataDirectory, fileName);

    // Return the first one that exists (prioritize extracted/downloaded data)
    const existsSync = require('fs').existsSync as (path: string) => boolean;
    for (const filePath of [extractedSubPath, extractedPath, dataPath, staticPath]) {
      if (existsSync(filePath)) {
        return filePath;
      }
    }

    // Fallback to static path
    return staticPath;
  }

  private parseProcessoLine(line: string): ProcessoEntity | null {
    const parts = line.split(';');
    if (parts.length < 12) return null;

    const dsProcesso = parts[0]?.trim();
    if (!dsProcesso) return null; // Skip if no process ID

    return {
      DSProcesso: dsProcesso,
      NRProcesso: parts[1]?.trim() || '',
      NRAnoProcesso: parts[2]?.trim() || '',
      BTAtivo: parts[3]?.trim() || '',
      NRNUP: parts[4]?.trim() || '',
      IDTipoRequerimento: parseInt(parts[5]) || 0,
      IDFaseProcesso: parseInt(parts[6]) || 0,
      IDUnidadeAdministrativaRegional: parseInt(parts[7]) || 0,
      IDUnidadeProtocolizadora: parseInt(parts[8]) || 0,
      DTProtocolo: parts[9]?.trim() || '',
      DTPrioridade: parts[10]?.trim() || '',
      QTAreaHA: parts[11]?.trim() || '',
    };
  }

  private parseFaseProcessoLine(line: string): FaseProcessoEntity | null {
    const parts = line.split(';');
    if (parts.length < 2) return null;

    return {
      IDFaseProcesso: parseInt(parts[0]) || 0,
      DSFaseProcesso: parts[1]?.trim() || '',
    };
  }

  private parseTipoRequerimentoLine(
    line: string,
  ): TipoRequerimentoEntity | null {
    const parts = line.split(';');
    if (parts.length < 2) return null;

    return {
      IDTipoRequerimento: parseInt(parts[0]) || 0,
      DSTipoRequerimento: parts[1]?.trim() || '',
    };
  }

  private parseMunicipioLine(line: string): MunicipioEntity | null {
    const parts = line.split(';');
    if (parts.length < 3) return null;

    return {
      IDMunicipio: parseInt(parts[0]) || 0,
      NMMunicipio: parts[1]?.trim() || '',
      SGUF: parts[2]?.trim() || '',
    };
  }

  private parseSubstanciaLine(line: string): SubstanciaEntity | null {
    const parts = line.split(';');
    if (parts.length < 2) return null;

    return {
      IDSubstancia: parseInt(parts[0]) || 0,
      NMSubstancia: parts[1]?.trim() || '',
    };
  }

  private parseProcessoMunicipioLine(
    line: string,
  ): ProcessoMunicipioEntity | null {
    const parts = line.split(';');
    if (parts.length < 2) return null;

    const dsProcesso = parts[0]?.trim();
    const idMunicipio = parseInt(parts[1]);
    
    if (!dsProcesso || !idMunicipio) return null;

    return {
      DSProcesso: dsProcesso,
      IDMunicipio: idMunicipio,
    };
  }

  private parseProcessoSubstanciaLine(
    line: string,
  ): ProcessoSubstanciaEntity | null {
    const parts = line.split(';');
    if (parts.length < 4) return null;

    const dsProcesso = parts[0]?.trim();
    const idSubstancia = parseInt(parts[1]);
    
    if (!dsProcesso || !idSubstancia) return null;

    return {
      DSProcesso: dsProcesso,
      IDSubstancia: idSubstancia,
      IDTipoUsoSubstancia: parseInt(parts[2]) || 0,
      IDMotivoEncerramentoSubstancia: parseInt(parts[3]) || 0,
    };
  }

  async getAllData(): Promise<{
    processos: ProcessoEntity[];
    fases: FaseProcessoEntity[];
    tipos: TipoRequerimentoEntity[];
    municipios: MunicipioEntity[];
    substancias: SubstanciaEntity[];
    processoMunicipios: ProcessoMunicipioEntity[];
    processoSubstancias: ProcessoSubstanciaEntity[];
  }> {
    this.logger.log('Parsing all SCM data files...');

    const [
      processos,
      fases,
      tipos,
      municipios,
      substancias,
      processoMunicipios,
      processoSubstancias,
    ] = await Promise.all([
      this.parseProcessoFile(),
      this.parseFaseProcessoFile(),
      this.parseTipoRequerimentoFile(),
      this.parseMunicipioFile(),
      this.parseSubstanciaFile(),
      this.parseProcessoMunicipioFile(),
      this.parseProcessoSubstanciaFile(),
    ]);

    this.logger.log('Completed parsing all SCM data files');

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

  async loadDataToDatabase(): Promise<void> {
    this.logger.log('Loading CSV data to database (filtering for Ceará only)...');
    
    try {
      // Parse all CSV files
      this.logger.log('Step 1/7: Parsing CSV files...');
      const data = await this.getAllData();
      
      // Filter data for Ceará only
      this.logger.log('Step 2/7: Filtering data for Ceará (CE) only...');
      const filteredData = await this.filterDataForCeara(data);
      
      this.logger.log(`Original data: ${data.processos.length} processos, ${data.processoMunicipios.length} proc-municipios`);
      this.logger.log(`Filtered data: ${filteredData.processos.length} processos, ${filteredData.processoMunicipios.length} proc-municipios`);
      this.logger.log(`Reference tables: ${filteredData.fases.length} fases, ${filteredData.tipos.length} tipos, ${filteredData.municipios.length} municípios CE`);
      
      // Load reference tables first (no foreign keys)
      this.logger.log('Step 3/7: Loading reference tables...');
      await this.repositoryService.bulkInsertFaseProcesso(filteredData.fases);
      await this.repositoryService.bulkInsertTipoRequerimento(filteredData.tipos);
      await this.repositoryService.bulkInsertMunicipios(filteredData.municipios);
      await this.repositoryService.bulkInsertSubstancias(filteredData.substancias);
      
      // Load main table with chunking
      this.logger.log('Step 4/7: Loading processos do Ceará...');
      await this.repositoryService.bulkInsertProcessos(filteredData.processos);
      
      // Load relationship tables last
      this.logger.log('Step 5/7: Loading processo-município relationships...');
      await this.repositoryService.bulkInsertProcessoMunicipios(filteredData.processoMunicipios);
      
      this.logger.log('Step 6/7: Loading processo-substância relationships...');
      await this.repositoryService.bulkInsertProcessoSubstancias(filteredData.processoSubstancias);
      
      this.logger.log('Step 7/7: Finalizing database operations...');
      
      // Log final counts
      const counts = await this.repositoryService.getDataCounts();
      this.logger.log('Database loading completed for Ceará!');
      this.logger.log(`Final counts: ${JSON.stringify(counts, null, 2)}`);
      
    } catch (error) {
      this.logger.error('Failed to load data to database:', error);
      this.logger.error('Error details:', error.stack);
      throw error;
    }
  }

  private async filterDataForCeara(data: any) {
    this.logger.log('Filtering data for Ceará municipalities...');
    
    // Filter municipalities for Ceará only (SGUF = 'CE')
    const municipiosCE = data.municipios.filter(m => m.SGUF === 'CE');
    const municipiosCEIds = new Set(municipiosCE.map(m => m.IDMunicipio));
    
    this.logger.log(`Found ${municipiosCE.length} municipalities in Ceará`);
    
    // Filter processo-município relationships for Ceará municipalities
    const processoMunicipiosCE = data.processoMunicipios.filter(pm => 
      municipiosCEIds.has(pm.IDMunicipio)
    );
    
    // Get unique process IDs that are in Ceará
    const processosIdsNoceara = new Set(processoMunicipiosCE.map(pm => pm.DSProcesso));
    
    // Filter processes for Ceará only
    const processosCE = data.processos.filter(p => 
      processosIdsNoceara.has(p.DSProcesso)
    );
    
    // Filter processo-substancia relationships for Ceará processes
    const processoSubstanciasCE = data.processoSubstancias.filter(ps => 
      processosIdsNoceara.has(ps.DSProcesso)
    );
    
    // Get unique substance IDs used in Ceará
    const substanciasIdsNoceara = new Set(processoSubstanciasCE.map(ps => ps.IDSubstancia));
    const substanciasCE = data.substancias.filter(s => 
      substanciasIdsNoceara.has(s.IDSubstancia)
    );
    
    this.logger.log(`Ceará filter results:`);
    this.logger.log(`- Municípios: ${municipiosCE.length}`);
    this.logger.log(`- Processos: ${processosCE.length}`);
    this.logger.log(`- Substâncias: ${substanciasCE.length}`);
    this.logger.log(`- Proc-Municípios: ${processoMunicipiosCE.length}`);
    this.logger.log(`- Proc-Substâncias: ${processoSubstanciasCE.length}`);
    
    return {
      processos: processosCE,
      fases: data.fases, // Keep all phases (small table)
      tipos: data.tipos, // Keep all types (small table)
      municipios: municipiosCE,
      substancias: substanciasCE,
      processoMunicipios: processoMunicipiosCE,
      processoSubstancias: processoSubstanciasCE,
    };
  }

  async isDataLoadedInDatabase(): Promise<boolean> {
    return this.repositoryService.hasData();
  }
}
