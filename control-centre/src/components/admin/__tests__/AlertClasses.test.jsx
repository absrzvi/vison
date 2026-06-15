// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AlertClasses } from '../AlertClasses';

vi.mock('../../../api/alertClasses', () => ({
  listAlertClasses: vi.fn(),
  disableAlertClass: vi.fn(),
  enableAlertClass: vi.fn(),
}));

import { listAlertClasses, disableAlertClass, enableAlertClass } from '../../../api/alertClasses';

const BODY = {
  alert_classes: [
    { alert_code: 'UNATTENDED_BAG', state: 'disabled', disabled_by: 'claudia', disabled_at: '2026-06-15 10:00', enabled_by: null, enabled_at: null },
    { alert_code: 'slip_fall', state: 'enabled', disabled_by: null, disabled_at: null, enabled_by: 'claudia', enabled_at: '2026-06-15 09:00' },
  ],
};

beforeEach(() => vi.clearAllMocks());

describe('AlertClasses — three states', () => {
  it('shows loading first', () => {
    listAlertClasses.mockReturnValue(new Promise(() => {}));
    render(<AlertClasses />);
    expect(screen.getByTestId('alert-classes-loading')).toBeInTheDocument();
  });

  it('shows error + retry when the list fails', async () => {
    listAlertClasses.mockRejectedValueOnce(Object.assign(new Error('boom'), { status: 500 }));
    render(<AlertClasses />);
    expect(await screen.findByTestId('alert-classes-error')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('boom');
  });

  it('renders the populated list with state pills', async () => {
    listAlertClasses.mockResolvedValueOnce(BODY);
    render(<AlertClasses />);
    expect(await screen.findByTestId('alert-classes-screen')).toBeInTheDocument();
    expect(screen.getByText('UNATTENDED_BAG')).toBeInTheDocument();
    expect(screen.getByText('slip_fall')).toBeInTheDocument();
    // disabled class shows an Enable button; enabled class shows a Disable button
    expect(screen.getByTestId('alert-classes-toggle-UNATTENDED_BAG')).toHaveTextContent('Enable');
    expect(screen.getByTestId('alert-classes-toggle-slip_fall')).toHaveTextContent('Disable');
  });

  it('renders the empty state when no classes have been toggled', async () => {
    listAlertClasses.mockResolvedValueOnce({ alert_classes: [] });
    render(<AlertClasses />);
    expect(await screen.findByTestId('alert-classes-screen')).toBeInTheDocument();
    expect(screen.getByText(/all classes are active/i)).toBeInTheDocument();
  });
});

describe('AlertClasses — mutations', () => {
  it('disabling an enabled class posts disable and refetches', async () => {
    listAlertClasses.mockResolvedValue(BODY);
    disableAlertClass.mockResolvedValueOnce({ alert_code: 'slip_fall', state: 'disabled' });
    render(<AlertClasses />);
    await screen.findByTestId('alert-classes-screen');

    fireEvent.click(screen.getByTestId('alert-classes-toggle-slip_fall'));

    await waitFor(() => expect(disableAlertClass).toHaveBeenCalledWith('slip_fall'));
    // refetch after toggle (initial load + post-toggle reload)
    await waitFor(() => expect(listAlertClasses).toHaveBeenCalledTimes(2));
  });

  it('enabling a disabled class posts enable', async () => {
    listAlertClasses.mockResolvedValue(BODY);
    enableAlertClass.mockResolvedValueOnce({ alert_code: 'UNATTENDED_BAG', state: 'enabled' });
    render(<AlertClasses />);
    await screen.findByTestId('alert-classes-screen');

    fireEvent.click(screen.getByTestId('alert-classes-toggle-UNATTENDED_BAG'));

    await waitFor(() => expect(enableAlertClass).toHaveBeenCalledWith('UNATTENDED_BAG'));
  });

  it('surfaces a mutation error (e.g. 403) without crashing', async () => {
    listAlertClasses.mockResolvedValue(BODY);
    disableAlertClass.mockRejectedValueOnce(Object.assign(new Error('Insufficient role'), { status: 403 }));
    render(<AlertClasses />);
    await screen.findByTestId('alert-classes-screen');

    fireEvent.click(screen.getByTestId('alert-classes-toggle-slip_fall'));
    expect(await screen.findByText('Insufficient role')).toBeInTheDocument();
  });
});
