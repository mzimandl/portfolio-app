import React from 'react';
import { AbstractSection, SectionProps } from '../../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow } from '../Settings';


interface DataRow {
    date: string;
    ticker: string;
    amount: number;
    fee: number;
    currency: string;
}

interface NewDataRow {
    date: string;
    ticker: string;
    amount: string;
    fee: string;
}

type DepositsResponse = Array<DataRow>;

interface DepositsState {
    deposits: Array<DataRow>;
    instruments: Array<InstrumentDataRow>;
}

interface DepositsProps {}
interface NewDepositProps {
    deposits:Array<InstrumentDataRow>;
    addDeposit:(newDeposit: NewDataRow) => void;
}

class NewDepositTableRow extends React.Component<NewDepositProps, NewDataRow> {

    constructor(props: NewDepositProps) {
        super(props);
        this.state = {
            date: '',
            ticker: '',
            amount: '',
            fee: '',
        };
    }

    render() {
        return <TableRow>
            <TableCell>
                <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({date: e.target.value})} />
            </TableCell>
            <TableCell>
                <FormControl fullWidth size='small'>
                    <InputLabel id="ticker-select-label">Ticker</InputLabel>
                    <Select
                        labelId='ticker-select-label'
                        value={this.state.ticker}
                        label="Ticker"
                        onChange={(e) => this.setState({ticker: e.target.value})}
                    >
                        {this.props.deposits
                            .filter(v => v.evaluation === 'manual')
                            .map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)
                        }
                    </Select>
                </FormControl>
            </TableCell>
            <TableCell>
                <TextField label="Amount" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({amount: e.target.value})} />
            </TableCell>
            <TableCell>
                <TextField label="Fee" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({fee: e.target.value})} />
            </TableCell>
            <TableCell><IconButton onClick={e => this.props.addDeposit(this.state)}><AddBox/></IconButton></TableCell>
        </TableRow>
    }
}

export class Deposits extends AbstractSection<DepositsProps, DepositsState> {

    sectionName = () => 'Values';

    constructor(props: DepositsProps & SectionProps) {
        super(props);
        this.state = {
            deposits: [],
            instruments: [],
        };

        this.addDeposit = this.addDeposit.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadInstruments().then(() =>
            this.loadValues().then(() =>
                this.props.displayProgressBar(false)
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then<Array<InstrumentDataRow>>(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadValues = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/deposits/list?${params.toString()}`)
            .then<DepositsResponse>(res => res.json())
            .then(deposits => this.setState({deposits}));
    }

    addDeposit = (newDeposit: NewDataRow) => {
        if (newDeposit.ticker && newDeposit.date && (newDeposit.amount || newDeposit.fee)) {
            this.props.displayProgressBar(true);
            fetch('/deposits/new', {method: 'POST', body: JSON.stringify(newDeposit)})
                .then(res => {
                    this.loadValues().then(() => {
                        this.props.displayProgressBar(false);
                    });
                });
        }
    }

    render() {

        return <Box>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <NewDepositTableRow deposits={this.state.instruments} addDeposit={this.addDeposit} />
                    </TableHead>
                    <TableBody>
                        {this.state.deposits.map(
                            (item, i) => <TableRow key={i}>
                                <TableCell>{item.date}</TableCell>
                                <TableCell>{item.ticker}</TableCell>
                                <TableCell>{this.formatCurrency(item.amount, {currency: item.currency})}</TableCell>
                                <TableCell colSpan={2}>{this.formatCurrency(item.fee, {currency: item.currency})}</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    }
}