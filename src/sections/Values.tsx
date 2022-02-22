import { AbstractSection, SectionProps } from '../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow } from './Settings';


interface DataRow {
    date: string;
    ticker: string;
    value: number;
    currency: string;
}

interface NewDataRow {
    date: string;
    ticker: string;
    value: string;
}

type ValuesResponse = Array<DataRow>;

interface ValuesState {
    values: Array<DataRow>;
    newValue: NewDataRow;
    instruments: Array<InstrumentDataRow>;
}

interface ValuesProps {}

export class Values extends AbstractSection<ValuesProps, ValuesState> {

    sectionName = () => 'Values';

    constructor(props: ValuesProps & SectionProps) {
        super(props);
        this.state = {
            values: [],
            instruments: [],
            newValue: {
                date: '',
                ticker: '',
                value: '',
            }
        };

        this.addValue = this.addValue.bind(this);
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
        return fetch(`/values/list?${params.toString()}`)
            .then<ValuesResponse>(res => res.json())
            .then(values => this.setState({values}));
    }

    addValue = () => {
        if (this.state.newValue.ticker && this.state.newValue.date && this.state.newValue.value) {
            this.props.displayProgressBar(true);
            fetch('/values/new', {method: 'POST', body: JSON.stringify(this.state.newValue)})
                .then(res => {
                    this.setState({
                        newValue: {
                            date: '',
                            ticker: '',
                            value: '',
                        }
                    });
                    this.loadValues().then(() => this.props.displayProgressBar(false));
                });
        }
    }

    render() {

        return <Box>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>
                                <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                                onChange={(e) => this.setState({newValue: {...this.state.newValue, date: e.target.value}})} />
                            </TableCell>
                            <TableCell>
                                <FormControl fullWidth size='small'>
                                    <InputLabel id="ticker-select-label">Ticker</InputLabel>
                                    <Select
                                        labelId='ticker-select-label'
                                        value={this.state.newValue.ticker}
                                        label="Ticker"
                                        onChange={(e) => this.setState({newValue: {...this.state.newValue, ticker: e.target.value}})}
                                    >
                                        {this.state.instruments.map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)}
                                    </Select>
                                </FormControl>
                            </TableCell>
                            <TableCell>
                                <TextField label="Value" variant="outlined" size='small' margin='none' fullWidth
                                onChange={(e) => this.setState({newValue: {...this.state.newValue, value: e.target.value}})} />
                            </TableCell>
                            <TableCell><IconButton onClick={this.addValue}><AddBox/></IconButton></TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {this.state.values.map(
                            (item, i) => <TableRow key={i}>
                                <TableCell>{item.date}</TableCell>
                                <TableCell>{item.ticker}</TableCell>
                                <TableCell colSpan={2}>{this.formatCurrency(item.value, item.currency)}</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    }
}