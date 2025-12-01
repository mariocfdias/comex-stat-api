import { Logger } from '@nestjs/common';
import axios from 'axios';
import { KeepaliveScheduler } from './keepalive.scheduler';

jest.mock('axios');

describe('KeepaliveScheduler', () => {
  let scheduler: KeepaliveScheduler;
  const mockedAxios = axios as jest.Mocked<typeof axios>;
  let warnSpy: jest.SpyInstance;
  let debugSpy: jest.SpyInstance;

  beforeEach(() => {
    warnSpy = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
    debugSpy = jest.spyOn(Logger.prototype, 'debug').mockImplementation(() => undefined);
    scheduler = new KeepaliveScheduler();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.clearAllMocks();
    delete process.env.SELF_PING_URL;
  });

  it('skips ping when SELF_PING_URL is not configured', async () => {
    await scheduler.handlePing();

    expect(mockedAxios.get).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith(
      'SELF_PING_URL is not set. Skipping keepalive ping.',
    );
  });

  it('pings the configured URL with a timeout', async () => {
    process.env.SELF_PING_URL = 'https://example.com';
    mockedAxios.get.mockResolvedValue({ data: 'ok' });

    await scheduler.handlePing();

    expect(mockedAxios.get).toHaveBeenCalledWith(
      'https://example.com',
      expect.objectContaining({ timeout: 5_000 }),
    );
  });

  it('logs a warning when the ping fails', async () => {
    process.env.SELF_PING_URL = 'https://example.com';
    mockedAxios.get.mockRejectedValue(new Error('boom'));

    await scheduler.handlePing();

    expect(warnSpy).toHaveBeenCalled();
    expect(debugSpy).not.toHaveBeenCalled();
  });
});
