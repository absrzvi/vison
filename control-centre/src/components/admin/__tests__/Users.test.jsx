// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { Users } from '../Users';

vi.mock('../../../api/users', () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  patchUser: vi.fn(),
  resetPassword: vi.fn(),
}));

import { listUsers, createUser, patchUser } from '../../../api/users';

const ROWS = [
  { user_id: 'u1', username: 'admin1', role: 'admin', is_active: true },
  { user_id: 'u2', username: 'op1', role: 'operator', is_active: true },
];

beforeEach(() => vi.clearAllMocks());

describe('Users — three states', () => {
  it('shows loading first', () => {
    listUsers.mockReturnValue(new Promise(() => {}));
    render(<Users />);
    expect(screen.getByTestId('users-loading')).toBeInTheDocument();
  });

  it('shows error + retry when the list fails', async () => {
    listUsers.mockRejectedValueOnce(Object.assign(new Error('boom'), { status: 500 }));
    render(<Users />);
    expect(await screen.findByTestId('users-error')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('boom');
  });

  it('renders the populated user list', async () => {
    listUsers.mockResolvedValueOnce(ROWS);
    render(<Users />);
    expect(await screen.findByTestId('users-screen')).toBeInTheDocument();
    expect(screen.getByText('admin1')).toBeInTheDocument();
    expect(screen.getByText('op1')).toBeInTheDocument();
  });
});

describe('Users — mutations', () => {
  it('create flow posts and refetches', async () => {
    listUsers.mockResolvedValue(ROWS);
    createUser.mockResolvedValueOnce({ user_id: 'u3' });
    render(<Users />);
    await screen.findByTestId('users-screen');

    fireEvent.click(screen.getByTestId('users-new'));
    fireEvent.change(screen.getByTestId('users-create-username'), { target: { value: 'newop' } });
    fireEvent.change(screen.getByTestId('users-create-password'), { target: { value: 'abcdefghijkl' } });
    fireEvent.click(screen.getByTestId('users-create-submit'));

    await waitFor(() =>
      expect(createUser).toHaveBeenCalledWith({ username: 'newop', password: 'abcdefghijkl', role: 'operator' })
    );
    // refetch after create (initial load + post-create reload)
    await waitFor(() => expect(listUsers).toHaveBeenCalledTimes(2));
  });

  it('surfaces a mutation error (e.g. last-admin 409) without crashing', async () => {
    listUsers.mockResolvedValue(ROWS);
    patchUser.mockRejectedValueOnce(Object.assign(new Error('Cannot remove the last active admin'), { status: 409 }));
    render(<Users />);
    await screen.findByTestId('users-screen');

    // Deactivate the admin row → server 409 surfaces as an alert.
    fireEvent.click(screen.getAllByText('Deactivate')[0]);
    expect(await screen.findByText('Cannot remove the last active admin')).toBeInTheDocument();
  });
});
