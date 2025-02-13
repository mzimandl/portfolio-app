import React from "react";
import { AbstractSection, numberIsValid, SectionProps } from '../../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow, InstrumentsResponse } from '../Settings';


interface DataRow {
    date: string;
    ticker: string;
    dividend: number;
}

interface NewDataRow {
    date: string;
    ticker: string;
    dividend: string;
}

type DividendsResponse = Array<DataRow>;

interface DividendsState {
    dividends: Array<DataRow>;
    instruments: Array<InstrumentDataRow>;
}

interface DividendsProps {}
interface NewDividendTableRowProps {
    instruments:Array<InstrumentDataRow>;
    addDividend:(newDividend:NewDataRow) => void;
}

class NewDividendTableRow extends React.Component<NewDividendTableRowProps, NewDataRow> {

    constructor(props:NewDividendTableRowProps) {
        super(props);
        this.state = {
            date: '',
            ticker: '',
            dividend: '0',
        }
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
                        {this.props.instruments.map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)}
                    </Select>
                </FormControl>
            </TableCell>
            <TableCell>
                <TextField value={this.state.dividend} label="Dividend" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => numberIsValid(e.target.value) ? this.setState({dividend: e.target.value}) : null} />
            </TableCell>
            <TableCell><IconButton onClick={e => this.props.addDividend(this.state)}><AddBox/></IconButton></TableCell>
        </TableRow>
    }
}

export class Dividends extends AbstractSection<DividendsProps, DividendsState> {

    sectionName = () => 'Dividends';

    constructor(props:DividendsProps & SectionProps) {
        super(props);
        this.state = {
            dividends: [],
            instruments: [],
        };

        this.addDividend = this.addDividend.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true);
        this.loadInstruments().then(() =>
            this.loadDividends().then(() =>
                this.props.displayProgressBar(false)
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then<InstrumentsResponse>(res => res.json())
            .then(instruments => this.setState({
                instruments: instruments.filter(item => !!item.dividend_currency)
            }));
    }

    loadDividends = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/dividends/list?${params.toString()}`)
            .then<DividendsResponse>(res => res.json())
            .then(dividends => this.setState({dividends}));
    }

    addDividend = (newDividend:NewDataRow) => {
        if (newDividend.ticker && newDividend.date) {
            this.props.displayProgressBar(true);
            fetch('/dividends/new', {method: 'POST', body: JSON.stringify(newDividend)})
                .then(res => {
                    this.loadDividends().then(() => {
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
                        <NewDividendTableRow instruments={this.state.instruments} addDividend={this.addDividend} />
                    </TableHead>
                    <TableBody>
                        {this.state.dividends.map(
                            (item, i) => <TableRow key={i}>
                                <TableCell>{item.date}</TableCell>
                                <TableCell>{item.ticker}</TableCell>
                                <TableCell colSpan={2}>{this.formatCurrency(item.dividend, {currency: this.state.instruments.find(v => v.ticker === item.ticker)?.dividend_currency})}</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    }
}