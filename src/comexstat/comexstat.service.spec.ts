import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { BadRequestException } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { TradeFlow } from './dto/comexstat.dto';
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

      const result = await service.getSummaryHistory({ from: '2024-01', to: '2024-03' });

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
        { period: 'jan/2024', exports: 1, imports: 0.2, tradeBalance: 0.8, tradeCurrent: 1.2 },
        { period: 'fev/2024', exports: 2, imports: 0.1, tradeBalance: 1.9, tradeCurrent: 2.1 },
        { period: 'mar/2024', exports: 0.5, imports: 0, tradeBalance: 0.5, tradeCurrent: 0.5 },
      ]);
      expect(cacheSet).toHaveBeenCalledTimes(1);
    });

    it('should throw when an invalid month format is provided', async () => {
      await expect(service.getSummaryHistory({ from: '2024-13', to: '2024-14' })).rejects.toBeInstanceOf(
        BadRequestException,
      );
      expect(httpMock.post).not.toHaveBeenCalled();
    });
  });
});
