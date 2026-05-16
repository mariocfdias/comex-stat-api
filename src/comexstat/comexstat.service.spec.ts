import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { BadRequestException } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { SummaryPeriod, TradeFlow } from './dto/comexstat.dto';
import { ComexstatService, COMEXSTAT_HTTP_CLIENT } from './comexstat.service';

describe('ComexstatService', () => {
  let service: ComexstatService;
  const httpMock = { post: jest.fn() };
  const cacheGet = jest.fn();
  const cacheSet = jest.fn();

  beforeEach(async () => {
    httpMock.post.mockReset();
    cacheGet.mockReset();
    cacheSet.mockReset();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ComexstatService,
        {
          provide: COMEXSTAT_HTTP_CLIENT,
          useValue: httpMock,
        },
        {
          provide: CACHE_MANAGER,
          useValue: {
            get: cacheGet,
            set: cacheSet,
          },
        },
      ],
    }).compile();

    service = module.get<ComexstatService>(ComexstatService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('getSummaryHistory', () => {
    it('should assemble summary data per month in the provided order', async () => {
      cacheGet.mockResolvedValue(undefined);
      cacheSet.mockResolvedValue(undefined);

      httpMock.post
        .mockResolvedValueOnce({
          data: {
            success: true,
            data: {
              list: [
                { year: 2024, monthNumber: 1, metricFOB: 1_000_000 },
                { year: 2024, monthNumber: 2, metricFOB: 2_000_000 },
                { year: 2024, monthNumber: 3, metricFOB: 500_000 },
              ],
            },
            message: null,
          },
        })
        .mockResolvedValueOnce({
          data: {
            success: true,
            data: {
              list: [
                { year: 2024, monthNumber: 1, metricFOB: 200_000 },
                { year: 2024, monthNumber: 2, metricFOB: 100_000 },
              ],
            },
            message: null,
          },
        });

      const result = await service.getSummaryHistory({
        from: '2024-01',
        to: '2024-03',
      });

      expect(httpMock.post).toHaveBeenCalledTimes(2);
      expect(httpMock.post).toHaveBeenNthCalledWith(
        1,
        '/general',
        {
          flow: TradeFlow.EXPORT,
          monthDetail: true,
          period: { from: '2024-01', to: '2024-03' },
          filters: [{ filter: 'state', values: [23] }],
          metrics: ['metricFOB'],
        },
        { params: { language: 'pt' } },
      );
      expect(httpMock.post).toHaveBeenNthCalledWith(
        2,
        '/general',
        {
          flow: TradeFlow.IMPORT,
          monthDetail: true,
          period: { from: '2024-01', to: '2024-03' },
          filters: [{ filter: 'state', values: [23] }],
          metrics: ['metricFOB', 'metricCIF'],
        },
        { params: { language: 'pt' } },
      );
      expect(result).toEqual([
        {
          period: 'jan/2024',
          exports: 1,
          imports: 0.2,
          tradeBalance: 0.8,
          tradeCurrent: 1.2,
        },
        {
          period: 'fev/2024',
          exports: 2,
          imports: 0.1,
          tradeBalance: 1.9,
          tradeCurrent: 2.1,
        },
        {
          period: 'mar/2024',
          exports: 0.5,
          imports: 0,
          tradeBalance: 0.5,
          tradeCurrent: 0.5,
        },
      ]);
      expect(cacheSet).toHaveBeenCalledTimes(1);
    });

    it('should throw when an invalid month format is provided', async () => {
      await expect(
        service.getSummaryHistory({ from: '2024-13', to: '2024-14' }),
      ).rejects.toBeInstanceOf(BadRequestException);
      expect(httpMock.post).not.toHaveBeenCalled();
    });
  });

  describe('getPartnerCountries', () => {
    it('should generate different queries for different custom periods', async () => {
      cacheGet.mockResolvedValue(undefined);
      cacheSet.mockResolvedValue(undefined);

      // Mock response for period 1 (2010-03 to 2010-05)
      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [
              { country: 'Estados Unidos', metricFOB: 91_578_285 },
              { country: 'Reino Unido', metricFOB: 24_042_518 },
            ],
          },
          message: null,
        },
      });

      const result1 = await service.getPartnerCountries(
        TradeFlow.EXPORT,
        SummaryPeriod.CUSTOM,
        { from: '2010-03', to: '2010-05' },
        10,
      );

      expect(httpMock.post).toHaveBeenCalledTimes(1);
      expect(httpMock.post).toHaveBeenCalledWith(
        '/general',
        {
          flow: TradeFlow.EXPORT,
          monthDetail: false,
          period: { from: '2010-03', to: '2010-05' },
          filters: [{ filter: 'state', values: [23] }],
          details: ['country'],
          metrics: ['metricFOB'],
        },
        { params: { language: 'pt' } },
      );

      expect(result1).toHaveLength(2);
      expect(result1[0].country).toBe('Estados Unidos');
      expect(result1[0].exports).toBeCloseTo(91.578285);

      // Verify cache key includes the actual period
      expect(cacheSet).toHaveBeenCalledTimes(1);
      const cacheKey1 = cacheSet.mock.calls[0][0];
      expect(cacheKey1).toContain('2010-03');
      expect(cacheKey1).toContain('2010-05');

      // Reset mocks for second test
      httpMock.post.mockReset();
      cacheGet.mockResolvedValue(undefined);
      cacheSet.mockReset();

      // Mock response for period 2 (2010-07 to 2010-09)
      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [
              { country: 'Estados Unidos', metricFOB: 104_275_131 },
              { country: 'Argentina', metricFOB: 39_986_445 },
            ],
          },
          message: null,
        },
      });

      const result2 = await service.getPartnerCountries(
        TradeFlow.EXPORT,
        SummaryPeriod.CUSTOM,
        { from: '2010-07', to: '2010-09' },
        10,
      );

      expect(httpMock.post).toHaveBeenCalledTimes(1);
      expect(httpMock.post).toHaveBeenCalledWith(
        '/general',
        {
          flow: TradeFlow.EXPORT,
          monthDetail: false,
          period: { from: '2010-07', to: '2010-09' },
          filters: [{ filter: 'state', values: [23] }],
          details: ['country'],
          metrics: ['metricFOB'],
        },
        { params: { language: 'pt' } },
      );

      expect(result2).toHaveLength(2);
      expect(result2[0].country).toBe('Estados Unidos');
      expect(result2[0].exports).toBeCloseTo(104.275131);

      // Verify cache key includes the actual period and is different
      expect(cacheSet).toHaveBeenCalledTimes(1);
      const cacheKey2 = cacheSet.mock.calls[0][0];
      expect(cacheKey2).toContain('2010-07');
      expect(cacheKey2).toContain('2010-09');
      expect(cacheKey1).not.toBe(cacheKey2);

      // Verify that different periods returned different results
      expect(result1[0].exports).not.toBe(result2[0].exports);
    });

    it('should support LAST_YEAR period type', async () => {
      cacheGet.mockResolvedValue(undefined);
      cacheSet.mockResolvedValue(undefined);

      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [
              { country: 'Estados Unidos', metricFOB: 500_000_000 },
            ],
          },
          message: null,
        },
      });

      const result = await service.getPartnerCountries(
        TradeFlow.EXPORT,
        SummaryPeriod.LAST_YEAR,
        undefined,
        10,
      );

      expect(httpMock.post).toHaveBeenCalledTimes(1);

      // Should query the full previous year
      const call = httpMock.post.mock.calls[0];
      const requestBody = call[1];

      // Extract year from the period
      const yearMatch = requestBody.period.from.match(/^(\d{4})-/);
      expect(yearMatch).toBeTruthy();
      const year = parseInt(yearMatch[1]);

      // Verify it's querying a full year (Jan to Dec)
      expect(requestBody.period.from).toBe(`${year}-01`);
      expect(requestBody.period.to).toBe(`${year}-12`);

      expect(result).toHaveLength(1);
      expect(result[0].country).toBe('Estados Unidos');
    });
  });

  describe('getStatesRanking', () => {
    it('should return states ranking with additional information', async () => {
      cacheGet.mockResolvedValue(undefined);
      cacheSet.mockResolvedValue(undefined);

      // Mock national total response
      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [{ metricFOB: 1_000_000_000 }],
          },
          message: null,
        },
      });

      // Mock states response
      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [
              { state: 'Ceará', metricFOB: 500_000_000 },
              { state: 'São Paulo', metricFOB: 300_000_000 },
            ],
          },
          message: null,
        },
      });

      // Mock sectors by state response
      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [
              {
                state: 'Ceará',
                ISICSection: 'Manufatura',
                coIsicSection: '01',
                metricFOB: 300_000_000,
              },
              {
                state: 'Ceará',
                ISICSection: 'Agricultura',
                coIsicSection: '02',
                metricFOB: 200_000_000,
              },
              {
                state: 'São Paulo',
                ISICSection: 'Serviços',
                coIsicSection: '03',
                metricFOB: 200_000_000,
              },
            ],
          },
          message: null,
        },
      });

      // Mock partners by state response
      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [
              { state: 'Ceará', country: 'Estados Unidos', metricFOB: 250_000_000 },
              { state: 'Ceará', country: 'China', metricFOB: 150_000_000 },
              { state: 'São Paulo', country: 'Argentina', metricFOB: 180_000_000 },
            ],
          },
          message: null,
        },
      });

      // Mock products by state response
      httpMock.post.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            list: [
              {
                state: 'Ceará',
                headingCode: '0101',
                heading: 'Produto A',
                metricFOB: 200_000_000,
              },
              {
                state: 'Ceará',
                headingCode: '0102',
                heading: 'Produto B',
                metricFOB: 100_000_000,
              },
              {
                state: 'São Paulo',
                headingCode: '0103',
                heading: 'Produto C',
                metricFOB: 150_000_000,
              },
            ],
          },
          message: null,
        },
      });

      const result = await service.getStatesRanking(TradeFlow.EXPORT, {
        from: '2024-01',
        to: '2024-12',
      });

      expect(httpMock.post).toHaveBeenCalledTimes(5);
      expect(result).toHaveLength(2);

      // Verify first state (Ceará)
      expect(result[0].rank).toBe(1);
      expect(result[0].state).toBe('Ceará');
      expect(result[0].value).toBeCloseTo(500); // 500_000_000 / 1_000_000 = 500
      expect(result[0].participation).toBeCloseTo(50); // 50% of national total

      // Verify top sectors
      expect(result[0].topSectors).toBeDefined();
      expect(result[0].topSectors?.length).toBeGreaterThan(0);
      expect(result[0].topSectors?.[0].name).toBe('Manufatura');
      expect(result[0].topSectors?.[0].value).toBeCloseTo(300);

      // Verify top partners
      expect(result[0].topPartners).toBeDefined();
      expect(result[0].topPartners?.length).toBeGreaterThan(0);
      expect(result[0].topPartners?.[0].country).toBe('Estados Unidos');

      // Verify top products
      expect(result[0].topProducts).toBeDefined();
      expect(result[0].topProducts?.length).toBeGreaterThan(0);
      expect(result[0].topProducts?.[0].description).toBe('Produto A');

      // Verify second state (São Paulo)
      expect(result[1].rank).toBe(2);
      expect(result[1].state).toBe('São Paulo');
      expect(result[1].participation).toBeCloseTo(30);
    });
  });
});
